# Place AI model files here (too large for GitHub)
# 
# Required files:
#   iemocap_trained/confidence_model.pt        (~360 MB)
#   iemocap_trained/tone_model.pt              (~360 MB)
#   ravdess/wav2vec2_ravdess_multitask_best.pt (~360 MB)
#
# These models are trained using Wav2Vec2-base and fine-tuned on:
#   - IEMOCAP dataset (tone & confidence scoring)
#   - RAVDESS dataset (multi-task emotion + confidence)
#
# See behavioral_analysis.py for architecture details.
