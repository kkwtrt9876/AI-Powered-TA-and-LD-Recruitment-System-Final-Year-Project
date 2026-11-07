"""
behavioral_analysis.py — Multi-Dataset Fused Behavioral Scoring

Audited and corrected against actual training notebooks:
  - IEMOCAP:  notebooke03e16d3c8.ipynb  → tone_model.pt, confidence_model.pt
  - RAVDESS:  Untitled6 (1).ipynb       → wav2vec2_ravdess_multitask_best.pt

AUDIT FINDINGS:
=============================================================
MODEL          | ENCODER        | FROZEN?              | PREPROC        | TARGET SCALE
IEMOCAP Tone   | wav2vec2-base  | partial (last 6 on)  | mean-std / 6s  | 4-class classification
IEMOCAP Conf   | wav2vec2-base  | partial (last 6 on)  | mean-std / 6s  | raw dominance 1–5
RAVDESS Multi  | wav2vec2-base  | fully frozen (layers 10-11 unfrozen during fine-tune) | max-abs / 3s | confidence = binary {0,1}

BUGS FIXED:
  [1] Shared encoder across IEMOCAP models → each gets its OWN Wav2Vec2Model instance
  [2] Confidence IEMOCAP scale was wrong (was dividing by 5.0, now correctly (val-1)/4)
  [3] RAVDESS model was not in pipeline → ADDED with sigmoid confidence & emotion sentiment
  [4] Preprocessing mismatch between IEMOCAP (mean-std) and RAVDESS (max-abs) → now model-specific
  [5] RAVDESS uses max_duration=3s (not 6s) → fixed
  [6] RAVDESS confidence is 0-1 binary probability via sigmoid → used directly
=============================================================
"""

import os
import io
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import librosa
import cv2
from pydub import AudioSegment
from fer.fer import FER
from transformers import Wav2Vec2Model, Wav2Vec2Processor

# Set ffmpeg path dynamically for pydub
AudioSegment.converter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")


# =============================================================
# SECTION 1: MODEL ARCHITECTURES (matching training exactly)
# =============================================================

class ToneClassifier(nn.Module):
    """
    IEMOCAP Tone model. Trained with partial encoder fine-tuning (last 6 layers).
    Architecture EXACTLY as in notebooke03e16d3c8.ipynb.
    """
    def __init__(self, encoder, num_classes=4, dropout=0.2, unfreeze_last_n_layers=6):
        super().__init__()
        self.encoder = encoder
        # Match training freeze pattern
        for p in self.encoder.feature_extractor.parameters():
            p.requires_grad = False
        for i in range(len(self.encoder.encoder.layers) - unfreeze_last_n_layers):
            for p in self.encoder.encoder.layers[i].parameters():
                p.requires_grad = False
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(encoder.config.hidden_size, num_classes)

    def forward(self, input_values):
        # Attention mask: mask padded zeros
        attention_mask = (input_values != 0).long()
        outputs = self.encoder(input_values, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state.mean(dim=1)
        return self.classifier(self.dropout(pooled))


class ConfidenceRegressor(nn.Module):
    """
    IEMOCAP Confidence model. Predicts raw dominance on 1–5 scale.
    Architecture EXACTLY as in notebooke03e16d3c8.ipynb.
    """
    def __init__(self, encoder, dropout=0.2, unfreeze_last_n_layers=6):
        super().__init__()
        self.encoder = encoder
        # Match training freeze pattern
        for p in self.encoder.feature_extractor.parameters():
            p.requires_grad = False
        for i in range(len(self.encoder.encoder.layers) - unfreeze_last_n_layers):
            for p in self.encoder.encoder.layers[i].parameters():
                p.requires_grad = False
        self.dropout = nn.Dropout(dropout)
        self.regressor = nn.Linear(encoder.config.hidden_size, 1)

    def forward(self, input_values):
        attention_mask = (input_values != 0).long()
        outputs = self.encoder(input_values, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state.mean(dim=1)
        return self.regressor(self.dropout(pooled)).squeeze(-1)


class Wav2Vec2ForEmotionConfidence(nn.Module):
    """
    RAVDESS Multitask model. EXACTLY as in Untitled6 (1).ipynb.
    Encoder is fully frozen (fine-tuning was done on layers 10 & 11 during training).
    For inference we reload the saved state_dict which already has the trained weights.
    emotion_head: 768 → 256 → 8 classes
    confidence_head: 768 → 128 → 1 (binary, sigmoid at inference)
    """
    def __init__(self, wav2vec_model_name="facebook/wav2vec2-base", num_emotions=8):
        super().__init__()
        self.wav2vec = Wav2Vec2Model.from_pretrained(wav2vec_model_name)

        # Freeze all — state_dict load will restore the trained values
        for param in self.wav2vec.parameters():
            param.requires_grad = False

        hidden_size = self.wav2vec.config.hidden_size  # 768

        self.emotion_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_emotions)
        )
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 1)
        )

    def forward(self, input_values):
        outputs = self.wav2vec(input_values).last_hidden_state  # [B, T, H]
        pooled = outputs.mean(dim=1)  # [B, H]
        emotion_logits = self.emotion_head(pooled)   # [B, 8]
        confidence_logits = self.confidence_head(pooled)  # [B, 1]
        return emotion_logits, confidence_logits


# =============================================================
# SECTION 2: PREPROCESSING (model-specific, matching training)
# =============================================================

IEMOCAP_SR = 16000
IEMOCAP_DURATION = 6  # seconds
RAVDESS_SR = 16000
RAVDESS_DURATION = 3  # seconds


def preprocess_iemocap(path: str, device: str) -> torch.Tensor:
    """
    Preprocessing that matches IEMOCAP training:
    - soundfile load
    - mono conversion
    - resample to 16kHz
    - mean-std normalization
    - trim/pad to 6 seconds
    - returns [1, 96000] tensor
    """
    try:
        audio = AudioSegment.from_file(path)
        # Convert to mono and 16kHz
        audio = audio.set_channels(1).set_frame_rate(IEMOCAP_SR)
        samples = np.array(audio.get_array_of_samples())
        if audio.sample_width == 2:
            waveform = samples.astype(np.float32) / 32768.0
        elif audio.sample_width == 4:
            waveform = samples.astype(np.float32) / 2147483648.0
        else:
            waveform = samples.astype(np.float32)
        sr = audio.frame_rate
    except Exception as e:
        print(f"[BehavioralAnalyzer] IEMOCAP audio load failed: {e}")
        waveform = np.zeros(IEMOCAP_SR * IEMOCAP_DURATION, dtype=np.float32)
        sr = IEMOCAP_SR

    # Mean-std normalize (matches training)
    waveform = (waveform - waveform.mean()) / (waveform.std() + 1e-7)

    # Trim / pad
    num_samples = IEMOCAP_SR * IEMOCAP_DURATION
    if len(waveform) > num_samples:
        waveform = waveform[:num_samples]
    else:
        waveform = np.pad(waveform, (0, num_samples - len(waveform)))

    tensor = torch.from_numpy(waveform).float().unsqueeze(0)  # [1, 96000]
    return tensor.to(device)


def preprocess_ravdess(path: str, processor: Wav2Vec2Processor, device: str) -> torch.Tensor:
    """
    Preprocessing that matches RAVDESS training:
    - soundfile load
    - mono conversion
    - resample to 16kHz
    - max-abs normalization (matches training exactly)
    - trim/pad to 3 seconds
    - Wav2Vec2Processor applied
    - returns [1, 48000] tensor
    """
    try:
        audio = AudioSegment.from_file(path)
        audio = audio.set_channels(1).set_frame_rate(RAVDESS_SR)
        samples = np.array(audio.get_array_of_samples())
        if audio.sample_width == 2:
            waveform = samples.astype(np.float32) / 32768.0
        elif audio.sample_width == 4:
            waveform = samples.astype(np.float32) / 2147483648.0
        else:
            waveform = samples.astype(np.float32)
        sr = audio.frame_rate
    except Exception as e:
        print(f"[BehavioralAnalyzer] RAVDESS audio load failed: {e}")
        waveform = np.zeros(RAVDESS_SR * RAVDESS_DURATION, dtype=np.float32)
        sr = RAVDESS_SR

    # Max-abs normalize (matches training)
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val

    # Trim / pad to 3 seconds
    max_len = RAVDESS_SR * RAVDESS_DURATION
    if len(waveform) > max_len:
        waveform = waveform[:max_len]
    else:
        waveform = np.pad(waveform, (0, max_len - len(waveform)))

    # Processor (same as training's RAVDESSDataset)
    inputs = processor(waveform, sampling_rate=RAVDESS_SR, return_tensors="pt")
    return inputs.input_values.to(device)


# =============================================================
# SECTION 3: RAVDESS EMOTION → TONE SENTIMENT MAPPING
# =============================================================

# RAVDESS label order from training notebook
RAVDESS_ID_TO_EMOTION = {
    0: "neutral",
    1: "calm",
    2: "happy",
    3: "sad",
    4: "angry",
    5: "fearful",
    6: "disgust",
    7: "surprised"
}

# Positive-tone weight per RAVDESS class (0-1 scale)
RAVDESS_TONE_WEIGHTS = {
    "neutral":   0.75,
    "calm":      0.90,
    "happy":     1.00,
    "sad":       0.30,
    "angry":     0.10,
    "fearful":   0.20,
    "disgust":   0.10,
    "surprised": 0.60
}

# IEMOCAP label map (confirmed from training output)
# {'ang': 0, 'fru': 1, 'hap': 2, 'neu': 3}
IEMOCAP_TONE_WEIGHTS = {
    0: 0.20,  # ang
    1: 0.40,  # fru
    2: 1.00,  # hap
    3: 0.80,  # neu
}


# =============================================================
# SECTION 4: BEHAVIORAL ANALYZER
# =============================================================

class BehavioralAnalyzer:
    """
    Multi-dataset fused behavioral scoring.
    - IEMOCAP: ToneClassifier + ConfidenceRegressor (each with INDEPENDENT encoder)
    - RAVDESS: Wav2Vec2ForEmotionConfidence (Tone + Confidence multi-task)
    - Fusion: Tone_final = 0.6 * Tone_iemocap + 0.4 * Tone_ravdess
               Conf_final = 0.6 * Conf_iemocap + 0.4 * Conf_ravdess
    - Video: FER-based facial sentiment
    """

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[BehavioralAnalyzer] Using device: {self.device}")

        # Shared processor for Wav2Vec2
        self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")

        # Paths
        base_path = os.path.dirname(os.path.abspath(__file__))
        iemocap_dir = os.path.join(base_path, "models", "iemocap trained files")
        ravdess_dir = os.path.join(base_path, "models", "ravdess")

        # --- IEMOCAP MODELS ---
        # FIX [1]: Each model gets its OWN independent encoder instance
        # to prevent weight overwriting when state_dicts are loaded
        print("[BehavioralAnalyzer] Loading IEMOCAP Tone model...")
        tone_encoder = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base").to(self.device)
        self.tone_model = ToneClassifier(tone_encoder, num_classes=4).to(self.device)
        tone_path = os.path.join(iemocap_dir, "tone_model.pt")
        if os.path.exists(tone_path):
            self.tone_model.load_state_dict(
                torch.load(tone_path, map_location=self.device, weights_only=True)
            )
            print("[BehavioralAnalyzer] tone_model.pt loaded OK")
        else:
            print(f"[BehavioralAnalyzer] WARNING: tone_model.pt not found at {tone_path}")
        self.tone_model.eval()

        print("[BehavioralAnalyzer] Loading IEMOCAP Confidence model...")
        conf_encoder = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base").to(self.device)
        self.conf_model = ConfidenceRegressor(conf_encoder).to(self.device)
        conf_path = os.path.join(iemocap_dir, "confidence_model.pt")
        if os.path.exists(conf_path):
            self.conf_model.load_state_dict(
                torch.load(conf_path, map_location=self.device, weights_only=True)
            )
            print("[BehavioralAnalyzer] confidence_model.pt loaded OK")
        else:
            print(f"[BehavioralAnalyzer] WARNING: confidence_model.pt not found at {conf_path}")
        self.conf_model.eval()

        # --- RAVDESS MODEL ---
        print("[BehavioralAnalyzer] Loading RAVDESS multitask model...")
        self.ravdess_model = Wav2Vec2ForEmotionConfidence(
            wav2vec_model_name="facebook/wav2vec2-base",
            num_emotions=8
        ).to(self.device)
        ravdess_path = os.path.join(ravdess_dir, "wav2vec2_ravdess_multitask_best.pt")
        if os.path.exists(ravdess_path):
            self.ravdess_model.load_state_dict(
                torch.load(ravdess_path, map_location=self.device, weights_only=True)
            )
            print("[BehavioralAnalyzer] wav2vec2_ravdess_multitask_best.pt loaded OK")
        else:
            print(f"[BehavioralAnalyzer] WARNING: RAVDESS model not found at {ravdess_path}")
        self.ravdess_model.eval()

        # --- VIDEO DETECTOR ---
        self.video_detector = FER(mtcnn=True)
        print("[BehavioralAnalyzer] Initialization complete.")

    # ----------------------------------------------------------
    # AUDIO INFERENCE
    # ----------------------------------------------------------

    def _infer_iemocap(self, path: str):
        """
        Returns (tone_0to1, conf_0to1) from IEMOCAP models for one audio file.
        """
        tensor = preprocess_iemocap(path, self.device)  # [1, 96000]

        with torch.no_grad():
            # --- Tone ---
            tone_logits = self.tone_model(tensor)
            probs = F.softmax(tone_logits, dim=1)[0]  # [4]
            tone_score = sum(IEMOCAP_TONE_WEIGHTS[i] * probs[i].item() for i in range(4))
            # tone_score is already in [0, 1] as it's a weighted sum of probs

            # --- Confidence ---
            # FIX [2]: Training targets were raw dominance 1-5. Normalize correctly.
            raw_dom = self.conf_model(tensor).item()
            # Clip to training range and normalize to [0, 1]
            raw_dom = max(1.0, min(5.0, raw_dom))
            conf_score = (raw_dom - 1.0) / 4.0  # maps [1,5] → [0,1]

        return float(tone_score), float(conf_score)

    def _infer_ravdess(self, path: str):
        """
        Returns (tone_0to1, conf_0to1) from RAVDESS model for one audio file.
        """
        tensor = preprocess_ravdess(path, self.processor, self.device)  # [1, 48000]

        with torch.no_grad():
            emotion_logits, confidence_logits = self.ravdess_model(tensor)

            # --- Tone from RAVDESS emotions ---
            probs = F.softmax(emotion_logits, dim=1)[0]  # [8]
            tone_score = sum(
                RAVDESS_TONE_WEIGHTS[RAVDESS_ID_TO_EMOTION[i]] * probs[i].item()
                for i in range(8)
            )

            # --- Confidence: binary probability via sigmoid ---
            # FIX [6]: Training used BCEWithLogitsLoss → inference uses sigmoid
            conf_score = torch.sigmoid(confidence_logits).item()

        return float(tone_score), float(conf_score)

    def analyze_audio(self, audio_paths: list):
        """
        Runs both IEMOCAP and RAVDESS models on all audio files.
        Fuses results with weighted average.
        Returns (avg_tone_0to1, avg_conf_0to1)

        FUSION WEIGHTS:
            Tone_final = 0.6 * Tone_iemocap + 0.4 * Tone_ravdess
            Conf_final = 0.6 * Conf_iemocap + 0.4 * Conf_ravdess
        """
        if not audio_paths:
            return 0.5, 0.5

        tone_fused_list = []
        conf_fused_list = []

        for path in audio_paths:
            if not os.path.exists(path):
                print(f"[BehavioralAnalyzer] Skipping missing: {path}")
                continue

            try:
                tone_i, conf_i = self._infer_iemocap(path)
            except Exception as e:
                print(f"[BehavioralAnalyzer] IEMOCAP inference error on {path}: {e}")
                tone_i, conf_i = 0.5, 0.5

            try:
                tone_r, conf_r = self._infer_ravdess(path)
            except Exception as e:
                print(f"[BehavioralAnalyzer] RAVDESS inference error on {path}: {e}")
                tone_r, conf_r = 0.5, 0.5

            # Weighted fusion
            tone_fused = 0.6 * tone_i + 0.4 * tone_r
            conf_fused = 0.6 * conf_i + 0.4 * conf_r

            # Clip to [0, 1]
            tone_fused = max(0.0, min(1.0, tone_fused))
            conf_fused = max(0.0, min(1.0, conf_fused))

            tone_fused_list.append(tone_fused)
            conf_fused_list.append(conf_fused)

        if not tone_fused_list:
            return 0.5, 0.5

        avg_tone = sum(tone_fused_list) / len(tone_fused_list)
        avg_conf = sum(conf_fused_list) / len(conf_fused_list)

        return round(avg_tone, 4), round(avg_conf, 4)

    # ----------------------------------------------------------
    # VIDEO INFERENCE
    # ----------------------------------------------------------

    def analyze_video(self, video_path: str) -> float:
        """
        FER-based facial sentiment analysis from session video.
        Samples 1 frame per second (up to 120 frames).
        Returns a sentiment score in [0, 1].
        """
        if not video_path or not os.path.exists(video_path):
            return 0.5

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        sample_rate = max(1, int(fps))

        scores = []
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                result = self.video_detector.detect_emotions(frame)
                if result:
                    e = result[0]['emotions']
                    # Weighted sentiment score
                    sentiment = (
                        e.get('happy', 0)    * 1.00 +
                        e.get('neutral', 0)  * 0.75 +
                        e.get('surprise', 0) * 0.60 +
                        e.get('sad', 0)      * 0.30 +
                        e.get('fear', 0)     * 0.20 +
                        e.get('angry', 0)    * 0.10 +
                        e.get('disgust', 0)  * 0.10
                    )
                    scores.append(sentiment)

            frame_idx += 1
            if len(scores) >= 120:
                break

        cap.release()

        if not scores:
            return 0.5

        avg = sum(scores) / len(scores)
        return round(max(0.0, min(1.0, avg)), 4)

    # ----------------------------------------------------------
    # FINAL SCORE CALCULATION
    # ----------------------------------------------------------

    def calculate_final_score(self,
                               mcq_score,    mcq_denom=5,
                               short_score=0, short_denom=25,
                               coding_score=0, coding_denom=20,
                               avg_conf=0.5,
                               avg_tone=0.5,
                               avg_video=0.5):
        """
        Final = 0.70 * [0.20*(MCQ/5*100) + 0.30*(Short/25*100) + 0.50*(Coding/20*100)]
               + 0.30 * [0.40*(Conf*100)  + 0.35*(Tone*100)     + 0.25*(Video*100)]

        All behavioral inputs (avg_conf, avg_tone, avg_video) are in [0, 1].
        """
        mcq_pct    = (mcq_score    / mcq_denom    * 100) if mcq_denom    > 0 else 0.0
        short_pct  = (short_score  / short_denom  * 100) if short_denom  > 0 else 0.0
        coding_pct = (coding_score / coding_denom * 100) if coding_denom > 0 else 0.0

        conf_pct  = avg_conf  * 100
        tone_pct  = avg_tone  * 100
        video_pct = avg_video * 100

        knowledge_score  = 0.20 * mcq_pct + 0.30 * short_pct + 0.50 * coding_pct
        behavioral_score = 0.40 * conf_pct + 0.35 * tone_pct + 0.25 * video_pct
        final_score      = 0.70 * knowledge_score + 0.30 * behavioral_score

        return {
            "final_score":       round(final_score, 2),
            "knowledge_score":   round(knowledge_score, 2),
            "behavioral_score":  round(behavioral_score, 2),
            "breakdown": {
                "mcq":        round(mcq_pct, 2),
                "short":      round(short_pct, 2),
                "coding":     round(coding_pct, 2),
                "confidence": round(conf_pct, 2),
                "tone":       round(tone_pct, 2),
                "video":      round(video_pct, 2)
            }
        }
