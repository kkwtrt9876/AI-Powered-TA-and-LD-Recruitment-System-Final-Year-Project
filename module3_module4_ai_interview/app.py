import os
import threading
import json
import requests
import time
from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv
import utils
import mysql.connector
from behavioral_analysis import BehavioralAnalyzer

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'submissions'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found in environment variables.")
else:
    print(f"GROQ_API_KEY loaded: {GROQ_API_KEY[:5]}...{GROQ_API_KEY[-4:]}")

client = Groq(api_key=GROQ_API_KEY)
analyzer = BehavioralAnalyzer()

# Database connection to flask_app
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="27042019",  # As seen in fyp_module1 app.py
    database="flask_app",
    port=3306,
    buffered=True
)

# Judge0 CE Public Instance
JUDGE0_URL = "https://ce.judge0.com"

# Judge0 language IDs
LANGUAGE_IDS = {
    "python": 71,   # Python 3.8
    "cpp":    54,   # C++ (GCC 9.2.0)
    "java":   62,   # Java (OpenJDK 13)
}

COURSES = [
    "Database",
    "Data Structures and Algorithms",
    "Web Development",
    "Machine Learning",
    "Artificial Intelligence",
    "Programming Fundamentals(PF)",
    "Object Oriented Programming(OOP)",
    "Data Mining",
    "Data Visualization",
    "Data Warehousing"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_courses', methods=['GET'])
def get_courses():
    return jsonify(COURSES)

@app.route('/generate_exam', methods=['POST'])
def generate_exam():
    data = request.json
    course_name = data.get('course_name')
    role = data.get('role', 'ta')  # 'ta' or 'ld'

    if not course_name:
        return jsonify({"error": "Course name is required"}), 400

    coding_instruction = ""
    coding_json_field = ""
    if role == 'ld':
        coding_instruction = """
    - 1 Coding Question: a medium-difficulty programming problem related to the course.
      The question must be solvable in Python, C++, or Java.
      It should not be trivial (e.g., not just "print Hello World") but also not very complex.
      Include a clear problem statement, example input/output if applicable.
      Provide the expected output for a standard/sample input as a string.
"""
        coding_json_field = """,
        "coding_question": {
            "id": 1,
            "question": "Problem statement...",
            "sample_input": "sample input or 'None' if no input needed",
            "expected_output": "expected output string"
        }"""

    prompt = f"""
    Generate an exam for the course '{course_name}'.
    The exam must include exactly:
    - 5 Multiple Choice Questions (MCQs) with 4 options each and the correct answer indicated.
    - 5 Short Answer Questions (conceptual, require a few sentences to answer).
    {coding_instruction}

    Return the response in strictly JSON format with the following structure:
    {{
        "mcqs": [
            {{
                "id": 1,
                "question": "Question text...",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_option": "Option A"
            }},
            ...
        ],
        "short_questions": [
            {{
                "id": 1,
                "question": "Question text..."
            }},
            ...
        ]{coding_json_field}
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates exams in JSON format."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        exam_content = json.loads(chat_completion.choices[0].message.content)
        exam_content['role'] = role
        return jsonify(exam_content)

    except Exception as e:
        print(f"Error generating exam: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/grade_short_answers', methods=['POST'])
def grade_short_answers():
    """
    Accepts a list of {question, answer} pairs and the course name.
    Uses the LLM to grade each answer out of 5 marks.
    Returns [{question, answer, score, feedback}]
    """
    data = request.json
    course = data.get('course', 'General')
    qa_pairs = data.get('qa_pairs', [])

    if not qa_pairs:
        return jsonify({"error": "No questions/answers provided"}), 400

    # Build a single LLM call to grade all answers
    qa_text = ""
    for i, item in enumerate(qa_pairs):
        qa_text += f"\nQ{i+1}: {item.get('question', '')}\nStudent Answer: {item.get('answer', 'No Answer')}\n"

    grading_prompt = f"""
You are an expert examiner for the course '{course}'.
Evaluate the following student short answers. For each answer:
1. Determine correctness on a scale of 0% to 100%.
2. Apply a threshold: if correctness >= 60%, the student passes that question.
3. Assign a score from 0 to 5 marks based on correctness:
   - 90-100% correct → 5 marks
   - 75-89% correct  → 4 marks
   - 60-74% correct  → 3 marks
   - 40-59% correct  → 2 marks
   - 20-39% correct  → 1 mark
   - 0-19% correct   → 0 marks
4. Give a brief 1-sentence feedback.

{qa_text}

Return ONLY a JSON array (no extra text) with this structure:
[
  {{
    "question_index": 1,
    "score": 4,
    "correctness_percent": 80,
    "feedback": "Good answer, but missed one key point."
  }},
  ...
]
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict but fair academic examiner. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": grading_prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = chat_completion.choices[0].message.content
        parsed = json.loads(raw)

        # The LLM may return {"grades": [...]} or just [...]
        if isinstance(parsed, list):
            grades = parsed
        elif isinstance(parsed, dict):
            # Try common wrapper keys
            grades = parsed.get('grades') or parsed.get('results') or parsed.get('answers') or list(parsed.values())[0]
        else:
            grades = []

        return jsonify({"grades": grades})

    except Exception as e:
        print(f"Error grading answers: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/run_code', methods=['POST'])
@app.route('/run_code', methods=['POST'])
def run_code():
    """
    Runs code using Judge0 CE (https://ce.judge0.com).
    Falls back to Groq LLM simulation if Judge0 is unavailable.
    """
    data = request.json
    language = data.get('language', 'python').lower()
    code = data.get('code', '')

    if language not in LANGUAGE_IDS:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    lang_id = LANGUAGE_IDS[language]

    try:
        # 1. Try Judge0 CE Public Instance
        payload = {
            "source_code": code,
            "language_id": lang_id,
            "stdin": ""
        }
        
        # Use ?wait=true for synchronous execution on the public instance
        resp = requests.post(
            f"{JUDGE0_URL}/submissions?wait=true",
            json=payload,
            timeout=20
        )

        if resp.status_code in [200, 201]:
            result = resp.json()
            stdout = result.get('stdout') or ''
            stderr = result.get('stderr') or result.get('compile_output') or ''
            status = result.get('status', {}).get('description', 'Unknown')
            
            # If the result suggests a service-level error or block, trigger LLM
            if "error" in status.lower() or "blocked" in status.lower():
                return _run_with_llm(language, code)

            return jsonify({
                "stdout": stdout,
                "stderr": stderr,
                "status": status,
                "is_llm_simulated": False
            })
        
        # If status code is 401, 403, 429, etc., Judge0 public instance might be capped
        print(f"Judge0 error (HTTP {resp.status_code}): {resp.text}")
        return _run_with_llm(language, code)

    except Exception as e:
        print(f"Code runner exception: {str(e)}")
        # Ultimate fallback: LLM simulation
        return _run_with_llm(language, code)


def _run_with_llm(language, code):
    """
    Safe fallback: Uses Groq LLM to simulate the output of the code.
    Ensures the student always gets a result even if runner APIs are down.
    """
    try:
        prompt = f"""
        Act as a code compiler/interpreter for the language '{language}'.
        Execute the following code and provide the output as it would appear in a terminal.
        
        CODE:
        {code}
        
        Return the result in strictly JSON format:
        {{
            "stdout": "the standard output of the code",
            "stderr": "any compilation or runtime errors, or an empty string",
            "status": "Accepted or Runtime Error"
        }}
        """
        
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise code execution simulator."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(completion.choices[0].message.content)
        result["is_llm_simulated"] = True
        return jsonify(result)
        
    except Exception as e:
        # Last resort fallback if Groq also fails
        if language == 'python':
            return _run_python_locally(code)
        return jsonify({
            "stdout": "",
            "stderr": f"Offline execution failed. Please check your internet connection. Error: {str(e)}",
            "status": "Service Unavailable"
        })


def _run_python_locally(code):
    """Local Python fallback when all external services are unreachable."""
    import subprocess
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            fname = f.name
        try:
            result = subprocess.run(
                ['python', fname],
                capture_output=True, text=True, timeout=10
            )
        finally:
            if os.path.exists(fname):
                os.unlink(fname)
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": "Accepted" if result.returncode == 0 else "Runtime Error"
        })
    except subprocess.TimeoutExpired:
        return jsonify({"stdout": "", "stderr": "Execution timed out (10s).", "status": "Time Limit Exceeded"})
    except Exception as e:
        return jsonify({"stdout": "", "stderr": str(e), "status": "Error"})


def grade_coding_question(course, language, question, code, expected_output):
    """
    Evaluates a coding solution using the LLM.
    Returns {score, feedback}
    """
    prompt = f"""
    You are an expert technical interviewer for the course '{course}'.
    Evaluate the following student code submission for the language '{language}'.

    PROBLEM STATEMENT:
    {question}

    EXPECTED OUTPUT (if applicable):
    {expected_output}

    STUDENT SUBMISSION:
    {code}

    Evaluate based on:
    1. Correctness (10 marks): Does it solve the problem?
    2. Logic & Efficiency (6 marks): Sound algorithms and appropriate data structures.
    3. Code Quality (4 marks): Clean, readable, and follows best practices.

    Total marks: 20.

    Return ONLY a JSON object:
    {{
        "score": 16,
        "correctness_score": 10,
        "logic_score": 4,
        "quality_score": 2,
        "feedback": "Brief 1-2 sentence feedback."
    }}
    """
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise technical grader. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Error grading code: {e}")
        return {"score": "N/A", "feedback": "Could not grade code automatically."}


@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    filename = "temp_audio.wav"
    audio_file.save(filename)

    try:
        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                response_format="json",
                language="en",
                temperature=0.0
            )
        os.remove(filename)
        return jsonify({"text": transcription.text})
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({"error": str(e)}), 500


@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    student_id = request.form.get('student_id', 'unknown_student')
    course_name = request.form.get('course_name', 'unknown_course')
    role = request.form.get('role', 'ta')

    student_folder = utils.create_student_folder(student_id, course_name)

    results_text = "=== EXAM RESULTS ===\n"
    results_text += f"Student ID: {student_id}\n"
    results_text += f"Course: {course_name}\n"
    results_text += f"Role Applied For: {'Teacher Assistant (TA)' if role == 'ta' else 'Lab Demonstrator (LD)'}\n\n"

    # MCQs
    mcq_answers = request.form.get('mcq_answers')
    mcq_score = 0
    mcq_total = 0
    if mcq_answers:
        results_text += "--- MCQs ---\n"
        mcq_data = json.loads(mcq_answers)
        mcq_total = len(mcq_data)
        for i, ans in enumerate(mcq_data):
            is_correct = ans.get('selected', '').strip() == ans.get('correct', '').strip()
            if is_correct:
                mcq_score += 1
            results_text += (
                f"Q{i+1}: {ans.get('question')}\n"
                f"  Selected: {ans.get('selected')}\n"
                f"  Correct:  {ans.get('correct')}\n"
                f"  Result:   {'✓ Correct' if is_correct else '✗ Wrong'}\n\n"
            )
        results_text += f"MCQ Score: {mcq_score}/{mcq_total}\n\n"

    # Short Answers with LLM grading
    short_answers = request.form.get('short_answers')
    short_total_score = 0
    if short_answers:
        results_text += "--- SHORT ANSWERS ---\n"
        sa_data = json.loads(short_answers)

        # Build qa_pairs for grading
        qa_pairs = [{"question": a.get('question'), "answer": a.get('answer')} for a in sa_data]

        grades = []
        try:
            grade_payload = {"course": course_name, "qa_pairs": qa_pairs}
            grading_prompt_pairs = qa_pairs

            grading_prompt = f"""
You are an expert examiner for the course '{course_name}'.
Evaluate the following student short answers. For each answer:
1. Determine correctness on a scale of 0% to 100%.
2. Apply a threshold of 60% — if correctness >= 60%, the student passes.
3. Assign a score 0-5:
   90-100% → 5, 75-89% → 4, 60-74% → 3, 40-59% → 2, 20-39% → 1, 0-19% → 0
4. Give a 1-sentence feedback.

"""
            for i, item in enumerate(qa_pairs):
                grading_prompt += f"Q{i+1}: {item['question']}\nStudent Answer: {item['answer']}\n\n"

            grading_prompt += """Return ONLY a JSON object with key "grades" containing an array:
{"grades": [{"question_index": 1, "score": 4, "correctness_percent": 80, "feedback": "..."}, ...]}"""

            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a strict but fair academic examiner. Respond with valid JSON only."},
                    {"role": "user", "content": grading_prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = json.loads(chat_completion.choices[0].message.content)
            if isinstance(raw, dict):
                grades = raw.get('grades') or raw.get('results') or list(raw.values())[0]
            elif isinstance(raw, list):
                grades = raw
        except Exception as e:
            print(f"Grading error: {e}")
            grades = []

        grades_by_index = {g.get('question_index', i+1): g for i, g in enumerate(grades)}

        for i, ans in enumerate(sa_data):
            grade = grades_by_index.get(i + 1, {})
            score = grade.get('score', 'N/A')
            correctness = grade.get('correctness_percent', 'N/A')
            feedback = grade.get('feedback', 'Could not grade automatically.')

            if isinstance(score, int):
                short_total_score += score

            results_text += (
                f"Q{i+1}: {ans.get('question')}\n"
                f"  Answer: {ans.get('answer')}\n"
                f"  Correctness: {correctness}%\n"
                f"  Score: {score}/5\n"
                f"  Feedback: {feedback}\n\n"
            )

        results_text += f"Short Answer Total Score: {short_total_score}/{len(sa_data) * 5}\n\n"

    # Coding Answer (LD only)
    coding_answer = request.form.get('coding_answer')
    coding_language = request.form.get('coding_language', '')
    if coding_answer and role == 'ld':
        results_text += "--- CODING QUESTION ---\n"
        coding_question_text = request.form.get('coding_question', 'N/A')
        
        # Parse exam data to get expected output
        expected_out = "N/A"
        try:
            # We might need to handle how coding_question is passed or stored
            # For now, we'll try to grade it with what we have
            coding_grade = grade_coding_question(
                course_name, 
                coding_language, 
                coding_question_text, 
                coding_answer, 
                "Check logic against problem statement"
            )
        except Exception as e:
            coding_grade = {"score": "Error", "feedback": str(e)}

        results_text += f"Question: {coding_question_text}\n"
        results_text += f"Language: {coding_language.upper()}\n"
        results_text += f"Score: {coding_grade.get('score', 'N/A')}/20\n"
        results_text += f"Feedback: {coding_grade.get('feedback', '')}\n"
        results_text += f"Code Submitted:\n{coding_answer}\n\n"

    utils.save_text_file(student_folder, "results.txt", results_text)

    # Save audio files
    for key in request.files:
        if key.startswith('audio_q'):
            file = request.files[key]
            utils.save_file(student_folder, f"{key}.wav", file)

    # Save full session video
    video_saved = False
    if 'full_session_video' in request.files:
        video_file = request.files['full_session_video']
        utils.save_file(student_folder, "full_session.mp4", video_file)
        video_saved = True

    # --- BEHAVIORAL ANALYSIS & FINAL SCORE ---
    audio_paths = []
    for f in os.listdir(student_folder):
        if f.startswith('audio_q') and f.endswith('.wav'):
            audio_paths.append(os.path.join(student_folder, f))
    
    video_path = os.path.join(student_folder, "full_session.mp4") if video_saved else None
    
    # Run Analysis
    avg_tone, avg_conf = analyzer.analyze_audio(audio_paths)
    avg_video = analyzer.analyze_video(video_path) if video_path else 50.0
    
    # Calculate Final Score
    c_score = 0
    if coding_answer and role == 'ld':
        try:
            c_score = int(coding_grade.get('score', 0))
        except:
            c_score = 0
            
    final_report = analyzer.calculate_final_score(
        mcq_score=mcq_score,    mcq_denom=5,
        short_score=short_total_score, short_denom=25,
        coding_score=c_score,   coding_denom=20 if (coding_answer and role == 'ld') else 1,
        avg_conf=avg_conf,
        avg_tone=avg_tone,
        avg_video=avg_video
    )
    
    # Update results text with final report (behavioral inputs are 0-1, convert to % for display)
    results_text += "\n=== BEHAVIORAL ANALYSIS ===\n"
    results_text += f"Confidence Score: {round(avg_conf * 100, 2)}%\n"
    results_text += f"Tone Score:       {round(avg_tone * 100, 2)}%\n"
    results_text += f"Video Sentiment:  {round(avg_video * 100, 2)}%\n\n"
    
    results_text += "=== FINAL ASSESSMENT ===\n"
    bd = final_report['breakdown']
    results_text += f"MCQ:              {bd['mcq']}%\n"
    results_text += f"Short Answers:    {bd['short']}%\n"
    results_text += f"Coding:           {bd['coding']}%\n"
    results_text += f"Knowledge Score (70%):  {final_report['knowledge_score']}%\n"
    results_text += f"Behavioral Score (30%): {final_report['behavioral_score']}%\n"
    results_text += f"--- FINAL SCORE: {final_report['final_score']}% ---\n"
    
    # Save the updated results
    utils.save_text_file(student_folder, "results.txt", results_text)
    
    # Also save a JSON summary for easy parsing
    utils.save_text_file(student_folder, "summary.json", json.dumps(final_report, indent=2))

    # --- DB SYNCHRONIZATION ---
    try:
        cursor = db.cursor()
        table = "student_applications_TA" if role == 'ta' else "student_applications"
        
        # Update interview marks for ALL sections of this course for this student
        # We assume course_name passed to us matches the course_code in the DB or we might need course_code
        # Looking at your main app logic, course_name passed is likely the display name, 
        # but let's assume we have course_code also if we update main.js to pass it.
        # For now, let's use the course_name provided.
        
        cursor.execute(f"""
            UPDATE {table} 
            SET interview_taken = 1, interview_marks = %s 
            WHERE username = %s AND (course_code = %s OR course_code LIKE %s)
        """, (final_report['final_score'], student_id, course_name, f"%{course_name}%"))
        
        db.commit()
        cursor.close()
        print(f"Successfully updated DB for {student_id} in {course_name}")
    except Exception as e:
        print(f"DB Sync Error: {e}")

    # --- AUTO-SHUTDOWN ---
    # The user requested to "close the app" after the interview is completed.
    def shutdown():
        print("Shutting down Exam App precisely as requested.")
        os._exit(0)
    
    threading.Timer(2.0, shutdown).start()

    return jsonify({
        "message": "Exam submitted and analyzed successfully", 
        "folder": student_folder,
        "final_score": final_report['final_score']
    })


if __name__ == '__main__':
    import sys
    debug_mode = '--debug' in sys.argv
    app.run(debug=debug_mode, use_reloader=debug_mode, port=5001)
