// ============================================================
// State
// ============================================================
let fullSessionRecorder;
let fullSessionChunks = [];
let stream;
let currentExamData = null;
let selectedRole = 'ta'; // 'ta' or 'ld'
let shortAnswerAudioBlobs = {};
let shortAnswerTranscriptions = {};
let selectedLanguage = 'python';

let examStage = 0; // 0:Setup, 1:Instructions, 2:MCQs, 3:ShortAnswers, 4:Coding(LD)
let examInProgress = false;

// ============================================================
// Security
// ============================================================
document.addEventListener("visibilitychange", () => {
    if (document.hidden && examInProgress) {
        alert("Academic Integrity Violation: Tab switch detected. Your exam is being submitted automatically.");
        submitExam(true);
    }
});

document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && examInProgress) {
        showModal('warning-modal');
    }
});

// ============================================================
// DOM Ready
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initCamera();

    const urlParams = new URLSearchParams(window.location.search);
    const uName = urlParams.get('username');
    const cName = urlParams.get('course_name');
    const rRole = urlParams.get('role');

    if (uName && cName && rRole) {
        // Auto-fill and bypass setup
        document.getElementById('student-id').value = uName;
        
        // Add course option since we skip loadCourses
        const select = document.getElementById('course-select');
        const opt = document.createElement('option');
        opt.value = cName;
        opt.textContent = cName;
        select.appendChild(opt);
        select.value = cName;

        selectedRole = rRole;
        const radio = document.getElementById(`role-${rRole}`);
        if (radio) radio.checked = true;

        // Skip directly to instructions
        proceedToInstructions();
    } else {
        loadCourses();
    }

    document.getElementById('setup-btn').addEventListener('click', proceedToInstructions);
    document.getElementById('start-test-btn').addEventListener('click', startTest);
    document.getElementById('next-btn').addEventListener('click', showShortAnswers);
    document.getElementById('short-next-btn').addEventListener('click', handleShortNext);
    document.getElementById('submit-exam-btn').addEventListener('click', () => submitExam(false));

    // Modal buttons
    document.getElementById('return-fullscreen-btn').addEventListener('click', returnToFullscreen);
    document.getElementById('agree-submit-btn').addEventListener('click', () => {
        hideModal('warning-modal');
        submitExam(true);
    });

    document.getElementById('confirm-cancel-btn').addEventListener('click', () => hideModal('confirm-modal'));

    // Language tab buttons
    document.querySelectorAll('.lang-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.lang-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            selectedLanguage = tab.dataset.lang;
            setBoilerplate(selectedLanguage);
        });
    });

    // Run button
    document.getElementById('run-btn').addEventListener('click', runCode);

    // Role selection — track visually
    document.querySelectorAll('input[name="role"]').forEach(radio => {
        radio.addEventListener('change', updateRoleCards);
    });
    updateRoleCards(); // initial state
});

function updateRoleCards() {
    document.querySelectorAll('.role-option').forEach(opt => {
        const radio = opt.querySelector('input[type="radio"]');
        const card = opt.querySelector('.role-card');
        if (radio.checked) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });
}

// ============================================================
// Fullscreen
// ============================================================
async function returnToFullscreen() {
    try {
        if (document.documentElement.requestFullscreen) {
            await document.documentElement.requestFullscreen();
        } else if (document.documentElement.webkitRequestFullscreen) {
            await document.documentElement.webkitRequestFullscreen();
        }
        document.getElementById('warning-modal').classList.remove('active');
    } catch (e) {
        console.error("Fullscreen failed:", e);
        alert("Could not return to fullscreen. Please try again.");
    }
}

// ============================================================
// Timer
// ============================================================
function startTimer() {
    let timeLeft = 300;

    const updateDisplay = (seconds) => {
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        const text = `Time Left: ${m}:${s}`;
        const el = document.getElementById('global-timer');
        if (el) {
            el.textContent = text;
            el.classList.toggle('danger-time', seconds <= 60);
        }
    };

    document.getElementById('global-timer').classList.remove('hidden');
    updateDisplay(timeLeft);

    const timerInterval = setInterval(() => {
        if (!examInProgress) { clearInterval(timerInterval); return; }
        timeLeft--;
        updateDisplay(timeLeft);
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            alert("Time is up! Submitting exam automatically.");
            submitExam(true);
        }
    }, 1000);
}

// ============================================================
// Camera
// ============================================================
async function initCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        document.getElementById('user-video').srcObject = stream;
        fullSessionRecorder = new MediaRecorder(stream);
        fullSessionRecorder.ondataavailable = e => {
            if (e.data.size > 0) fullSessionChunks.push(e.data);
        };
    } catch (err) {
        console.error("Error accessing media devices.", err);
        alert("Camera and Microphone access is required for this exam.");
    }
}

// ============================================================
// Courses
// ============================================================
async function loadCourses() {
    try {
        const response = await fetch('/exam_get_courses');
        const courses = await response.json();
        const select = document.getElementById('course-select');
        select.innerHTML = '<option value="">Select a Course</option>';
        courses.forEach(course => {
            const option = document.createElement('option');
            option.value = course;
            option.textContent = course;
            select.appendChild(option);
        });

        const checkInputs = () => {
            const studentId = document.getElementById('student-id').value.trim();
            const course = select.value;
            document.getElementById('setup-btn').disabled = !studentId || !course;
        };

        select.addEventListener('change', checkInputs);
        document.getElementById('student-id').addEventListener('input', checkInputs);
    } catch (error) {
        console.error('Error loading courses:', error);
    }
}

// ============================================================
// Navigation Flow
// ============================================================
function proceedToInstructions() {
    selectedRole = document.querySelector('input[name="role"]:checked').value;

    // Update instructions text dynamically
    const formatDesc = document.getElementById('format-description');
    if (formatDesc) {
        if (selectedRole === 'ld') {
            formatDesc.textContent = "The exam consists of 5 Multiple Choice Questions (MCQs), 5 Short Answer Questions (voice-recorded), and 1 Coding Challenge (Python / C++ / Java).";
        } else {
            formatDesc.textContent = "The exam consists of 5 Multiple Choice Questions (MCQs) and 5 Short Answer Questions (voice-recorded).";
        }
    }

    switchPanel('setup-panel', 'instruction-panel');
    examStage = 1;
}

async function startTest() {
    // Enforce fullscreen
    try {
        if (document.documentElement.requestFullscreen) {
            await document.documentElement.requestFullscreen();
        } else if (document.documentElement.webkitRequestFullscreen) {
            await document.documentElement.webkitRequestFullscreen();
        }
    } catch (e) {
        alert("Fullscreen mode is REQUIRED to start the exam. Please allow fullscreen.");
        return;
    }

    // Start recording
    fullSessionChunks = [];
    if (fullSessionRecorder && fullSessionRecorder.state === "inactive") {
        fullSessionRecorder.start(1000);
    }
    document.getElementById('rec-indicator').classList.remove('hidden');
    document.getElementById('instruction-panel').classList.add('hidden');
    document.getElementById('instruction-panel').classList.remove('active');

    try {
        const courseName = document.getElementById('course-select').value;
        const response = await fetch('/exam_generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ course_name: courseName, role: selectedRole })
        });

        if (!response.ok) throw new Error('Failed to generate exam');

        currentExamData = await response.json();
        renderMCQs(currentExamData.mcqs);
        renderShortAnswers(currentExamData.short_questions);
        if (selectedRole === 'ld' && currentExamData.coding_question) {
            renderCodingQuestion(currentExamData.coding_question);
        }

        switchPanel(null, 'mcq-panel');
        examStage = 2;
        examInProgress = true;
        document.getElementById('progress-container').classList.remove('hidden');
        updateProgress();
        startTimer();

    } catch (error) {
        console.error(error);
        alert("Failed to generate exam. Please try again.");
        document.exitFullscreen().catch(() => { });
        switchPanel(null, 'instruction-panel');
        if (fullSessionRecorder) fullSessionRecorder.stop();
        document.getElementById('rec-indicator').classList.add('hidden');
    }
}

function showShortAnswers() {
    switchPanel('mcq-panel', 'short-answer-panel');

    // Update the "Next" button in short-answer panel
    const shortNextBtn = document.getElementById('short-next-btn');
    if (selectedRole === 'ld') {
        shortNextBtn.textContent = 'Next: Coding Challenge';
    } else {
        shortNextBtn.textContent = 'Submit Exam';
    }
    examStage = 3;
}

function handleShortNext() {
    if (selectedRole === 'ld') {
        switchPanel('short-answer-panel', 'coding-panel');
        examStage = 4;
    } else {
        // TA: submit directly
        submitExam(false);
    }
}

function switchPanel(hideId, showId) {
    if (hideId) {
        const hide = document.getElementById(hideId);
        if (hide) {
            hide.classList.remove('active');
            setTimeout(() => hide.classList.add('hidden'), 400); // Wait for transition
        }
    }
    if (showId) {
        const show = document.getElementById(showId);
        if (show) {
            show.classList.remove('hidden');
            setTimeout(() => {
                show.classList.add('active');
                updateProgress();
            }, 50);
        }
    }
}

function updateProgress() {
    const bar = document.getElementById('progress-bar');
    const steps = ['step-mcq', 'step-short', 'step-coding', 'step-submit'];

    // Default weights
    let progress = 0;
    let activeIndex = -1;

    if (examStage === 2) { progress = 25; activeIndex = 0; }
    else if (examStage === 3) { progress = 50; activeIndex = 1; }
    else if (examStage === 4) { progress = 75; activeIndex = 2; }
    else if (examStage === 5) { progress = 100; activeIndex = 3; }

    if (bar) bar.style.width = `${progress}%`;

    steps.forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) {
            if (i <= activeIndex) el.classList.add('active');
            else el.classList.remove('active');
        }
    });

    // Hide coding step if not LD
    if (selectedRole !== 'ld') {
        const codingStep = document.getElementById('step-coding');
        if (codingStep) codingStep.style.display = 'none';
    }
}

function showModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function hideModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}

async function confirmAction(title, message) {
    return new Promise((resolve) => {
        document.getElementById('confirm-title').textContent = title;
        document.getElementById('confirm-message').textContent = message;
        showModal('confirm-modal');

        const proceedBtn = document.getElementById('confirm-proceed-btn');
        const cancelBtn = document.getElementById('confirm-cancel-btn');

        const onProceed = () => {
            cleanup();
            resolve(true);
        };
        const onCancel = () => {
            cleanup();
            resolve(false);
        };
        const cleanup = () => {
            proceedBtn.removeEventListener('click', onProceed);
            cancelBtn.removeEventListener('click', onCancel);
            hideModal('confirm-modal');
        };

        proceedBtn.addEventListener('click', onProceed);
        cancelBtn.addEventListener('click', onCancel);
    });
}

// ============================================================
// Rendering
// ============================================================
function renderMCQs(mcqs) {
    const container = document.getElementById('mcq-container');
    container.innerHTML = '';
    mcqs.forEach((q, index) => {
        const div = document.createElement('div');
        div.className = 'question-block';
        div.innerHTML = `
            <p class="question-text">${index + 1}. ${q.question}</p>
            <div class="options-list">
                ${q.options.map((opt, i) => `
                    <label class="option-item">
                        <input type="radio" name="mcq_${q.id}" value="${opt}">
                        <span class="option-label">${String.fromCharCode(65 + i)}.</span>
                        <span class="option-content">${opt}</span>
                    </label>
                `).join('')}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderShortAnswers(questions) {
    const container = document.getElementById('short-answer-container');
    container.innerHTML = '';
    questions.forEach((q, index) => {
        const div = document.createElement('div');
        div.className = 'question-block';
        div.innerHTML = `
            <p class="question-text">${index + 1}. ${q.question}</p>
            <div class="voice-answer-box">
                <div class="visualizer-container">
                    <canvas id="visualizer-${q.id}" width="200" height="50"></canvas>
                </div>
                <div class="controls-row">
                    <button class="record-btn" id="rec-btn-${q.id}" onclick="toggleRecording(${q.id})">
                        <i class="material-icons">mic</i> Record Answer
                    </button>
                    <div class="transcribed-text" id="transcription-${q.id}"></div>
                </div>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderCodingQuestion(q) {
    const box = document.getElementById('coding-question-box');
    let html = `
        <div class="coding-q-label">Problem Statement</div>
        <div class="coding-q-text">${q.question}</div>
    `;
    if (q.sample_input && q.sample_input !== 'None') {
        html += `<div class="coding-q-io"><strong>Sample Input:</strong> <code>${q.sample_input}</code></div>`;
    }
    if (q.expected_output) {
        html += `<div class="coding-q-io"><strong>Expected Output:</strong> <code>${q.expected_output}</code></div>`;
    }
    box.innerHTML = html;
    setBoilerplate('python');
}

// ============================================================
// Code Editor Boilerplate
// ============================================================
function setBoilerplate(lang) {
    const editor = document.getElementById('code-editor');
    const boilerplates = {
        python: `# Write your Python solution here\n\n`,
        cpp: `#include <iostream>\nusing namespace std;\n\nint main() {\n    // Write your C++ solution here\n    \n    return 0;\n}\n`,
        java: `public class Main {\n    public static void main(String[] args) {\n        // Write your Java solution here\n        \n    }\n}\n`
    };
    if (editor && editor.value.trim() === '' || editor.value.startsWith('//') || editor.value.startsWith('#') || editor.value.startsWith('public') || editor.value.startsWith('#include')) {
        editor.value = boilerplates[lang] || '';
    }
}

// ============================================================
// Run Code
// ============================================================
async function runCode() {
    const code = document.getElementById('code-editor').value;
    const outputEl = document.getElementById('code-output');
    const statusEl = document.getElementById('run-status');
    const runBtn = document.getElementById('run-btn');

    if (!code.trim()) {
        outputEl.textContent = '// Please write some code first.';
        return;
    }

    runBtn.disabled = true;
    runBtn.innerHTML = '<i class="material-icons">hourglass_empty</i> Running...';
    outputEl.textContent = '// Executing...';
    statusEl.textContent = '';
    statusEl.className = 'run-status';

    try {
        const response = await fetch('/exam_run_code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: selectedLanguage, code: code })
        });
        const result = await response.json();

        if (result.error) {
            outputEl.textContent = 'Error: ' + result.error;
            statusEl.textContent = 'Error';
            statusEl.classList.add('status-error');
        } else {
            const stdout = result.stdout || '';
            const stderr = result.stderr || '';
            const status = result.status || '';

            outputEl.textContent = stdout || (stderr ? '' : '(no output)');
            if (stderr) {
                outputEl.textContent += (stdout ? '\n\n--- Errors ---\n' : '') + stderr;
            }

            statusEl.textContent = status;
            if (status === 'Accepted') {
                statusEl.classList.add('status-ok');
            } else {
                statusEl.classList.add('status-error');
            }
        }
    } catch (e) {
        outputEl.textContent = 'Network error: ' + e.message;
    }

    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="material-icons">play_arrow</i> Run Code';
}

// ============================================================
// Audio Recording
// ============================================================
let currentRecorder = null;
let currentChunks = [];

window.toggleRecording = async function (questionId) {
    const btn = document.getElementById(`rec-btn-${questionId}`);
    const textDiv = document.getElementById(`transcription-${questionId}`);

    if (btn.classList.contains('recording')) {
        if (currentRecorder && currentRecorder.state !== 'inactive') {
            currentRecorder.stop();
        }
        btn.classList.remove('recording');
        btn.innerHTML = '<i class="material-icons">mic</i> Re-record Answer';
    } else {
        if (currentRecorder) {
            alert("Please finish the current recording first.");
            return;
        }
        currentChunks = [];
        currentRecorder = new MediaRecorder(stream);
        currentRecorder.ondataavailable = e => currentChunks.push(e.data);
        currentRecorder.onstop = async () => {
            const blob = new Blob(currentChunks, { type: 'audio/wav' });
            shortAnswerAudioBlobs[questionId] = blob;
            currentRecorder = null;

            textDiv.textContent = "Transcribing...";
            const formData = new FormData();
            formData.append('audio', blob, 'audio.wav');

            try {
                const response = await fetch('/exam_transcribe', { method: 'POST', body: formData });
                const result = await response.json();
                if (result.text) {
                    shortAnswerTranscriptions[questionId] = result.text;
                    textDiv.textContent = result.text;
                } else {
                    textDiv.textContent = "Error transcribing.";
                }
            } catch (e) {
                textDiv.textContent = "Error transcribing.";
            }
        };

        currentRecorder.start();
        visualizeAudio(stream, `visualizer-${questionId}`);
        btn.classList.add('recording');
        btn.innerHTML = '<i class="material-icons">stop</i> Stop Recording';
    }
};

// ============================================================
// Submission
// ============================================================
async function submitExam(autoSubmit = false) {
    if (!examInProgress && !autoSubmit) return;

    if (!autoSubmit) {
        const confirmed = await confirmAction("Submit Exam?", "Are you sure you want to finish your test? No changes can be made after submission.");
        if (!confirmed) return;
    }

    examStage = 5;
    updateProgress();

    if (fullSessionRecorder && fullSessionRecorder.state !== 'inactive') {
        fullSessionRecorder.stop();
        await new Promise(r => setTimeout(r, 500));
    }

    const submitBtn = document.getElementById('submit-exam-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="material-icons rotating">sync</i> Submitting...';
    }

    examInProgress = false;

    const formData = new FormData();
    formData.append('student_id', document.getElementById('student-id').value);
    formData.append('course_name', document.getElementById('course-select').value);
    formData.append('role', selectedRole);

    // MCQ Answers
    if (currentExamData && currentExamData.mcqs) {
        const mcqAnswers = currentExamData.mcqs.map(q => {
            const selected = document.querySelector(`input[name="mcq_${q.id}"]:checked`);
            return { id: q.id, question: q.question, selected: selected ? selected.value : "Not Answered", correct: q.correct_option };
        });
        formData.append('mcq_answers', JSON.stringify(mcqAnswers));
    }

    // Short Answers
    if (currentExamData && currentExamData.short_questions) {
        const shortAnswers = currentExamData.short_questions.map(q => ({
            id: q.id,
            question: q.question,
            answer: shortAnswerTranscriptions[q.id] || "No Answer Recorded"
        }));
        formData.append('short_answers', JSON.stringify(shortAnswers));

        for (const [qid, blob] of Object.entries(shortAnswerAudioBlobs)) {
            formData.append(`audio_q${qid}`, blob, `question_${qid}.wav`);
        }
    }

    // Coding Answer (LD only)
    if (selectedRole === 'ld') {
        const code = document.getElementById('code-editor') ? document.getElementById('code-editor').value : '';
        formData.append('coding_answer', code);
        formData.append('coding_language', selectedLanguage);
        if (currentExamData && currentExamData.coding_question) {
            formData.append('coding_question', currentExamData.coding_question.question || '');
        }
    }

    // Full Session Video
    const fullSessionBlob = new Blob(fullSessionChunks, { type: 'video/mp4' });
    formData.append('full_session_video', fullSessionBlob, 'full_session.mp4');

    try {
        const response = await fetch('/exam_submit', { method: 'POST', body: formData });
        await response.json();
        alert("Exam submitted successfully! Your short answers have been graded by AI. Results saved.");

        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => { });
        }
        
        // Redirect back to student welcome page
        const uName = document.getElementById('student-id').value;
        window.location.href = `/student_welcome/${uName}`;
    } catch (error) {
        console.error(error);
        alert("Error submitting exam. Please notify proctor.");
        submitBtns.forEach(b => { if (b) { b.textContent = "Submit Exam"; b.disabled = false; } });
    }
}

// ============================================================
// Audio Visualizer
// ============================================================
function visualizeAudio(stream, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const canvasCtx = canvas.getContext("2d");
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyzer = audioCtx.createAnalyser();
    analyzer.fftSize = 256;
    source.connect(analyzer);

    const bufferLength = analyzer.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        if (!currentRecorder || currentRecorder.state === 'inactive') {
            try { audioCtx.close(); } catch (e) { }
            return;
        }
        requestAnimationFrame(draw);
        analyzer.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = '#f0f0f0';
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let x = 0;
        for (let i = 0; i < bufferLength; i++) {
            const barHeight = dataArray[i] / 2;
            canvasCtx.fillStyle = `rgb(13, 71, 161)`;
            canvasCtx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
            x += barWidth + 1;
        }
    }
    draw();
}
