from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import mysql.connector
from datetime import datetime,timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import session
from datetime import timedelta

import random
import string
import json
import threading

import subprocess
import webbrowser
import time
import os
import requests as http_requests  # renamed to avoid conflict with flask.request

from groq import Groq
from dotenv import load_dotenv
from behavioral_analysis import BehavioralAnalyzer
import utils

# Load environment variables
load_dotenv()


app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.permanent_session_lifetime = timedelta(minutes=30)

from functools import wraps
from flask import redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response


@app.before_request
def session_timeout():
    if "username" in session:
        last_active_str = session.get("last_active")
        if last_active_str:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_active > timedelta(minutes=30):
                session.clear()
                return redirect(url_for("index"))

        # update session time
        session["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# DB connection — configure via environment variables in .env
db = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),    # set DB_PASSWORD in your .env
    database=os.getenv("DB_NAME", "flask_app"),
    port=int(os.getenv("DB_PORT", "3306")),
    buffered=True
)

cursor = db.cursor(dictionary=True)

# ============================================================
#  EXAM PROCTOR - Initialization (models load once at startup)
# ============================================================
print("[Exam Proctor] Initializing Groq client...")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found in environment variables.")
else:
    print(f"GROQ_API_KEY loaded: {GROQ_API_KEY[:5]}...{GROQ_API_KEY[-4:]}")

groq_client = Groq(api_key=GROQ_API_KEY)

print("[Exam Proctor] Loading BehavioralAnalyzer (AI models)...")
exam_analyzer = BehavioralAnalyzer()
print("[Exam Proctor] All models loaded successfully!")

app.config['UPLOAD_FOLDER'] = 'submissions'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

# Judge0 CE Public Instance
JUDGE0_URL = "https://ce.judge0.com"

# Judge0 language IDs
LANGUAGE_IDS = {
    "python": 71,   # Python 3.8
    "cpp":    54,   # C++ (GCC 9.2.0)
    "java":   62,   # Java (OpenJDK 13)
}

EXAM_COURSES = [
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

def grade_points(grade):
    gpa = 0.00
    if grade == "A+":
        gpa = 4.00
    elif grade == "A":
        gpa = 4.00
    elif grade == "A-":
        gpa = 3.67
    elif grade == "B+":
        gpa = 3.33
    elif grade == "B":
        gpa = 3.00
    elif grade == "B-":
        gpa = 2.67
    elif grade == "C+":
        gpa = 2.33
    elif grade == "C":
        gpa = 2.00
    elif grade == "C-":
        gpa = 1.67
    elif grade == "D+":
        gpa = 1.33
    elif grade == "D":
        gpa = 1.00
    else:
        gpa = 0.00   # default for F or invalid

    return gpa


# Keep track of the current scheduled job
CURRENT_JOB_ID = "result_calculation_job"
CURRENT_JOB_ID_TA = "result_calculation_job_TA"

scheduler = BackgroundScheduler()
scheduler.start()

def add_current_semester():
    now = datetime.now()
    month = now.month
    year = now.year

    if month == 1:
        semester_name = "Spring"
    elif month == 6:
        semester_name = "Summer"
    elif month == 8:
        semester_name = "Fall"
    else:
        # Not a semester starting month
        return

    semester_id = f"{semester_name} {year}"

    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM semester_id_data WHERE semester_id = %s", (semester_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (semester_id,))
        db.commit()
        print(f"Added new semester: {semester_id}")
    cursor.close()

# Run immediately on startup to catch missed semesters
add_current_semester()

# Schedule to run daily at midnight
scheduler.add_job(add_current_semester, 'cron', hour=0, minute=0)

# <---------------------------------------- LD FUNCTIONALITY ------------------------------------->

# this is the finalization steps , when the student is shown the results and he clicks on it, that he is willing to accept.

def finalize_ld_results(semester_id,launch_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * from ld_finalization WHERE sem_id = %s and launch_id =%s", (semester_id,launch_id))
    row = cursor.fetchall()

    # print(row)

    course_data = set()
    course_data_acceptance = set()

    for r in row:
        course_name = r['course_name']
        acceptance =r['acceptance']
        sem_id = r['sem_id']
        s_id = r['s_id']
        section = r['section']
        number = r['number']
        submission_files_path = r.get('submission_files_path')

        print(acceptance, " this is the acceptance")
        
        if acceptance == 1:
            cursor.execute(f"UPDATE lab_allocations SET allocation_count = allocation_count + 1 WHERE sem_id = %s and column_name=%s and section=%s", (sem_id,course_name,section))
            db.commit()

            if number == 1:
                cursor.execute("""
                    UPDATE lab_allocations 
                    SET s_id_one = %s, email_one = %s, confirmed_one = 1, submission_files_path = %s
                    WHERE sem_id = %s AND column_name = %s AND section = %s
                """, (s_id, f"{s_id}@nu.edu.pk", submission_files_path, sem_id, course_name, section))

                db.commit()

            if number == 2:
                cursor.execute("""
                    UPDATE lab_allocations 
                    SET s_id_two = %s, email_two = %s, confirmed_two = 1, submission_files_path1 = %s
                    WHERE sem_id = %s AND column_name = %s AND section = %s
                """, (s_id, f"{s_id}@nu.edu.pk", submission_files_path, sem_id, course_name, section))

                db.commit()



            cursor.execute(
            """
            UPDATE ld_course_details 
            SET counter_lds = counter_lds + 1
            WHERE sem_id = %s AND course_name = %s
            """,
            (sem_id, course_name)
            )
            db.commit() 

            # If no row was updated, insert instead
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO ld_course_details (sem_id, course_name, counter_lds)
                    VALUES (%s, %s, %s)
                    """,
                    (sem_id, course_name, 1)
                )

            if course_name not in course_data:
                print(acceptance, " this is the acceptance inside the else")

                cursor.execute(
                """
                UPDATE ld_course_details 
                SET launch_times = launch_times + 1
                WHERE sem_id = %s AND course_name = %s
                """,
                (sem_id, course_name)
                )

                db.commit()

                # If no row was updated, insert instead
                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO ld_course_details (sem_id, course_name, launch_times)
                        VALUES (%s, %s, %s)
                        """,
                        (sem_id, course_name, 1)
                    )
                
                course_data.add(course_name)



            cursor.execute(
            """
            UPDATE student_ld_counter 
            SET counter = counter + 1
            WHERE sem_id = %s AND s_id = %s
            """,
            (sem_id, s_id)
            )

            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO student_ld_counter (sem_id, s_id, counter)
                    VALUES (%s, %s, %s)
                    """,
                    (sem_id, s_id, 1)
                )

            db.commit()

        else:

            if course_name not in course_data:
                print(acceptance, " this is the acceptance inside the else")

                cursor.execute(
                """
                UPDATE ld_course_details 
                SET launch_times = launch_times + 1
                WHERE sem_id = %s AND course_name = %s
                """,
                (sem_id, course_name)
                )

                db.commit()

                # If no row was updated, insert instead
                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO ld_course_details (sem_id, course_name, launch_times)
                        VALUES (%s, %s, %s)
                        """,
                        (sem_id, course_name, 1)
                    )
                
                course_data.add(course_name)

            cursor.execute(
                """
                DELETE FROM ld_finalization
                WHERE sem_id = %s AND s_id = %s AND course_name = %s AND acceptance = %s AND launch_id = %s and section=%s and number = %s
                """,
                (sem_id, s_id, course_name, acceptance,launch_id,section,number)
            )
            db.commit()

# <------------------------------------ this is the schedule that will run the finalization steps ----------------------->
def schedule_ld_time_limit(launch_id,semester_id,time):

    # Remove existing job if present
    try:
        scheduler.remove_job(CURRENT_JOB_ID)
    except Exception:
        pass  # ignore if no job exists
    
    scheduler.add_job(
        func=finalize_ld_results,
        trigger='date',
        run_date=time,
        args=[semester_id,launch_id],
        id=f"finalize_{launch_id}",
        replace_existing=True
    )
    print(f"Scheduled finalization for ld acceptance his courses launch_id={launch_id} at {time}")

# ---------------- Helper function to sort and caulcaulate the results of the LDS----------------


def calculate_results(launch_id):
    """
    Finds best candidates for each course and section safely.
    """
    print('Job started')

    cursor = db.cursor(dictionary=True)
    now = datetime.now()
    month = now.month
    year = now.year

    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"

    # Ensure semester exists
    cursor.execute("SELECT semester_id FROM semester_id_data WHERE semester_id=%s", (current_semester,))
    _ = cursor.fetchall()  # ✅ Always fetch all results
    if not _:
        cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (current_semester,))
        db.commit()

    # Get applications
    cursor.execute("SELECT * FROM student_applications WHERE launch_id=%s", (launch_id,))
    applications = cursor.fetchall()
    cursor.fetchall()

    main_data = {}
    for app in applications:
        key = (app['course_code'], app['section'])
        main_data.setdefault(key, []).append({
            'id': app['username'],
            'time_apply': app['time_apply'],
            'interview_marks': app.get('interview_marks', 0),
            'submission_files_path': app.get('submission_files_path')
        })

    print("Grouped:", main_data)

    for (course_code, section), candidates in main_data.items():
        print(f"Processing {course_code} - {section}")

        # Enrich candidates
        for cand in candidates:
            # Use a fresh cursor for each query block — prevents overlap
            c = db.cursor(dictionary=True)

            # GPA
            c.execute("SELECT gpa FROM student_gpa WHERE s_id=%s", (cand['id'],))
            gpa_row = c.fetchone()
            cand['gpa'] = gpa_row['gpa'] if gpa_row else 0
            c.fetchall()  # ✅ ensures no unread results
            c.close()

            # Course grade
            c = db.cursor(dictionary=True)
            c.execute(f"SELECT {course_code} FROM student_studied_courses WHERE student_id=%s", (cand['id'],))
            grades = c.fetchall()
            grade = 0.0
            for g in grades:
                try:
                    points = grade_points(g[course_code].split(',')[1])
                    if points > grade:
                        grade = points
                except:
                    pass
            cand['grade'] = grade
            c.fetchall()
            c.close()
            

            # Base course grade
            base_course = course_code.split('_lab')[0]
            c = db.cursor(dictionary=True)
            c.execute(f"SELECT {base_course} FROM student_studied_courses WHERE student_id=%s", (cand['id'],))
            base_grades = c.fetchall()
            course_grade = 0.0
            for bg in base_grades:
                try:
                    points = grade_points(bg[base_course].split(',')[1])
                    if points > course_grade:
                        course_grade = points
                except:
                    pass
            cand['course_grade'] = course_grade
            c.close()

            # Seniority
            c = db.cursor(dictionary=True)
            c.execute("SELECT sem_id FROM student_studied_courses WHERE student_id=%s", (cand['id'],))
            sem_rows = c.fetchall()
            cand['senior'] = sum(1 for s in sem_rows if s['sem_id'].split()[0].lower() != 'summer')
            c.fetchall()
            c.close()

        # Filter GPA
        candidates = [c for c in candidates if c['gpa'] >= 2.5]
        if not candidates:
            continue

        sorted_candidates = sorted(
            candidates,
            key=lambda x: (-x['grade'], -x['course_grade'], -x['gpa'], -x['interview_marks'], -x['senior'], x['time_apply'])
        )

        top_1 = sorted_candidates[0] if len(sorted_candidates) > 0 else None
        top_2 = sorted_candidates[1] if len(sorted_candidates) > 1 else None

        # Allocation count
        c = db.cursor(dictionary=True)
        c.execute("SELECT allocation_count FROM lab_allocations WHERE sem_id=%s AND section=%s",
                  (current_semester, section))
        row = c.fetchone()
        counter = row['allocation_count'] if row else 0
        c.fetchall()
        c.close()

        # Insert
        if counter == 0:
            if top_1:
                c = db.cursor()
                c.execute("""
                    INSERT INTO ld_finalization (sem_id, s_id, course_name, launch_id, section, number, submission_files_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (current_semester, top_1['id'], course_code, launch_id, section, 1, top_1['submission_files_path']))
                
                c.close()
            if top_2:
                c = db.cursor()
                c.execute("""
                    INSERT INTO ld_finalization (sem_id, s_id, course_name, launch_id, section, number, submission_files_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (current_semester, top_2['id'], course_code, launch_id, section, 2, top_2['submission_files_path']))
                
                c.close()
            db.commit()

        elif counter == 1 and top_1:
            c = db.cursor()
            c.execute("""
                INSERT INTO ld_finalization (sem_id, s_id, course_name, launch_id, section, number, submission_files_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (current_semester, top_1['id'], course_code, launch_id, section, 2, top_1['submission_files_path']))
            
            db.commit()
            c.close()

    # Timeout acceptance
    run_time = datetime.now() + timedelta(minutes=3)
    cursor.execute("INSERT INTO ld_timeout_acceptance (launch_datetime, result_datetime) VALUES (%s, %s)",
                   (now, run_time))
    db.commit()
    
    schedule_ld_time_limit(launch_id, current_semester, run_time)

    print("Job completed successfully ✅")



def schedule_result_job(launch_id, result_time):
    """ Schedule the APScheduler job for result calculation """
    # Remove existing job if present
    try:
        scheduler.remove_job(CURRENT_JOB_ID)
    except Exception:
        pass  # ignore if no job exists

    scheduler.add_job(
        func=calculate_results,
        trigger='date',
        run_date=result_time,
        args=[launch_id],
        id=CURRENT_JOB_ID,
        replace_existing=True
    )
    print(f"Scheduled result calculation for launch_id={launch_id} at {result_time}")


# <---------------------------------------------------- END LD RESULT FUNCTIONLITY -------------------------------->

# <---------------------------------------------- TA RESULT FUNCTIONALITY ---------------------------------------->

def calculate_results_TA(launch_id):
    """
    Finds best candidates for each course and section safely.
    Saves results in TA_results table.
    """
    print('Job started')

    cursor = db.cursor(dictionary=True)
    now = datetime.now()
    month = now.month
    year = now.year

    # Determine current semester
    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"

    # Ensure semester exists
    cursor.execute("SELECT semester_id FROM semester_id_data WHERE semester_id=%s", (current_semester,))
    _ = cursor.fetchall()  # ✅ Always fetch all results
    if not _:
        cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (current_semester,))
        db.commit()

    # Get all applications for this launch
    cursor.execute("SELECT * FROM student_applications_TA WHERE launch_id=%s", (launch_id,))
    applications = cursor.fetchall()
    cursor.fetchall()

    # Group applications by (course_code, section)
    main_data = {}
    for app in applications:
        key = (app['course_code'], app['section'])
        main_data.setdefault(key, []).append({
            'id': app['username'],
            'time_apply': app['time_apply'],
            'interview_marks': app.get('interview_marks', 0),
            'submission_files_path': app.get('submission_files_path')
        })

    print("Grouped applications:", main_data)

    # Process each course-section
    for (course_code, section), candidates in main_data.items():
        print(f"Processing {course_code} - {section}")

        # Enrich candidates with GPA, grade, seniority
        for cand in candidates:
            cand['course_code'] = course_code
            cand['section'] = section

            # GPA
            c = db.cursor(dictionary=True)
            c.execute("SELECT gpa FROM student_gpa WHERE s_id=%s", (cand['id'],))
            gpa_row = c.fetchone()
            cand['gpa'] = gpa_row['gpa'] if gpa_row else 0
            c.fetchall()
            c.close()

            # Course grade
            c = db.cursor(dictionary=True)
            c.execute(f"SELECT {course_code} FROM student_studied_courses WHERE student_id=%s", (cand['id'],))
            grades = c.fetchall()
            grade = 0.0
            for g in grades:
                try:
                    points = grade_points(g[course_code].split(',')[1])
                    if points > grade:
                        grade = points
                except:
                    pass
            cand['grade'] = grade
            c.fetchall()
            c.close()

            # Seniority
            c = db.cursor(dictionary=True)
            c.execute("SELECT sem_id FROM student_studied_courses WHERE student_id=%s", (cand['id'],))
            sem_rows = c.fetchall()
            cand['senior'] = sum(1 for s in sem_rows if s['sem_id'].split()[0].lower() != 'summer')
            c.fetchall()
            c.close()

        # Filter GPA >= 2.5
        candidates = [c for c in candidates if c['gpa'] >= 2.5]
        if not candidates:
            continue

        # Sort candidates by grade, GPA, interview marks, seniority, earliest apply
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (-x['grade'], -x['gpa'], -x['interview_marks'], -x['senior'], x['time_apply'])
        )

        # Save results to DB
        print(f"Results for {course_code} - {section}:")
        for rank, cand in enumerate(sorted_candidates, start=1):
            print(f"Rank {rank}: {cand}")
            cursor.execute("""
                INSERT INTO TA_results_for_Teacher
                (semester, course_code, section, launch_id, student_id, time_apply, gpa, grade, seniority, rank_, submission_files_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                current_semester,
                course_code,
                section,
                launch_id,
                cand['id'],
                cand['time_apply'],
                cand['gpa'],
                cand['grade'],
                cand['senior'],
                rank,
                cand['submission_files_path']
            ))
        db.commit()

        print()  # Blank line for readability

def schedule_result_job_TA(launch_id, result_time):
    """ Schedule the APScheduler job for result calculation """
    # Remove existing job if present
    try:
        scheduler.remove_job(CURRENT_JOB_ID_TA)
    except Exception:
        pass  # ignore if no job exists

    scheduler.add_job(
        func=calculate_results_TA,
        trigger='date',
        run_date=result_time,
        args=[launch_id],
        id=CURRENT_JOB_ID_TA,
        replace_existing=True
    )
    print(f"Scheduled result calculation for launch_id={launch_id} at {result_time}")

# <------------------------------------------------ END OF TA RESULT CALCULATION--------------------------------------->

def check_and_schedule_latest_launch():
    """ Call this on app startup to schedule any pending result calculation """
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    if row:
        launch_id = row["id"]
        result_time = row["result_datetime"]
        now = datetime.now()
        if now < result_time:
            schedule_result_job(launch_id, result_time)
            print("Scheduler initialized on app startup.")


def check_and_schedule_latest_launch_TA():
    """ Call this on app startup to schedule any pending result calculation """
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    if row:
        launch_id = row["id"]
        result_time = row["result_datetime"]
        now = datetime.now()
        if now < result_time:
            schedule_result_job_TA(launch_id, result_time)
            print("Scheduler initialized on app startup.")



def check_and_schedule_latest_launch_for_ld():
    """ Call this on app startup to schedule any pending result calculation """

    now = datetime.now()
    month = now.month
    year = now.year

    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"


    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ld_timeout_acceptance ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()



    cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
    up_row = cursor.fetchone()

    cursor.close()
    if row:
        launch_id = up_row["id"]
        result_time = row["result_datetime"]
        now = datetime.now()
        if now < result_time:
            schedule_ld_time_limit(launch_id, current_semester,result_time)
            print("Scheduler initialized on app startup.")




# <-------------------------------------------------login and signup part of the app ---------------------------------->
@app.route("/")
def index():
    return render_template("index.html")

from flask import Flask, render_template, request, redirect, url_for

from flask import session

def upload_login_details(username, password, role, time):
    cursor = db.cursor(dictionary=True)
    
    # Prepare the INSERT query
    sql = """
        INSERT INTO login_details (username, password, role, time)
        VALUES (%s, %s, %s, %s)
    """
    
    # Execute the query with the provided values
    cursor.execute(sql, (username, password, role, time))
    
    # Commit the changes to the database
    db.commit()
    
    print(f"Login details for {username} inserted successfully.")





@app.route("/login", methods=["POST"])
def login():
    cursor = db.cursor(dictionary=True)
    username = request.form["username"]
    password = request.form["password"]
    role = request.form["role"]
    time = datetime.now()

    upload_login_details(username,password,role,time)

    user = None

    if role == "student":
        cursor.execute("SELECT * FROM students WHERE s_id=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        if user:
            # Store in session
            session.permanent = True
            session["username"] = username
            session["role"] = "student"
            return redirect(url_for("student_welcome", username=username))

    elif role == "admin":
        cursor.execute("SELECT * FROM admins WHERE a_id=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        if user:
            session.permanent = True
            session["username"] = username
            session["role"] = "admin"
            return redirect(url_for("welcome_admin", username=username))
        
    elif role == "teacher":
        cursor.execute("SELECT * FROM teacher_login WHERE id=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        if user:
            session.permanent = True
            session["username"] = username
            session["role"] = "teacher"
            return redirect(url_for("teacher_panel", username=username))

    return "<h2>Invalid login details!</h2><a href='/'>Go Back</a>"


@app.route("/teacher_panel")
@login_required
def teacher_panel():
    username = request.args.get("username")  # URL still works
    if username != session.get("username"):
        return redirect(url_for("index"))
    return render_template("teacher_panel.html", username=username)

@app.route("/student_welcome/<username>")
@login_required
def student_welcome(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    return render_template("student_welcome.html", username=username)

@app.route("/welcome_admin")
@login_required
def welcome_admin():
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    return render_template("welcome_admin.html")

@app.route("/signup", methods=["POST"])
def signup():
    cursor = db.cursor(dictionary=True)
    username = request.form["username"]
    password = request.form["password"]
    role = request.form["role"]

    cursor.execute("SELECT * FROM students WHERE s_id=%s", (username,))
    if cursor.fetchone():
        cursor.fetchall()  
        return "<h2>User already exists!</h2><a href='/'>Go Back</a>"
    else:
        cursor.execute("INSERT INTO students (s_id, password) VALUES (%s, %s)", (username, password))
        db.commit()

        # Store in session
        session.permanent = True
        session["username"] = username
        session["role"] = "student"

        return redirect(url_for("student_welcome", username=username))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))




# <------------------------------------------------------ END of LOGIN SIGNUP --------------------------------------->


@app.route("/profile/<username>", methods=["GET", "POST"])
@login_required
def profile(username):

    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT semester_id FROM semester_id_data")
    semester_ids = cursor.fetchall()

    # fetch all departments
    cursor.execute("SELECT dep_id, dep_name FROM departments")
    departments = cursor.fetchall()

    cursor.execute("SELECT name, column_name FROM helper_student_studied_courses")
    courses = cursor.fetchall()

    # get student's current department (if any)
    cursor.execute("""
        SELECT d.dep_id, d.dep_name
        FROM student_department sd
        JOIN departments d ON sd.dep_id = d.dep_id
        WHERE sd.s_id = %s
    """, (username,))
    record = cursor.fetchone()
    cursor.close()

    department_id = record["dep_id"] if record else None
    department_name = record["dep_name"] if record else None
    editable = False

    if request.method == "POST":
        if "edit" in request.form:
            editable = True
        elif "save" in request.form:

            cursor = db.cursor(dictionary=True)
            dep_value = request.form.get("department")

            # Handle both ID and name cases safely
            if dep_value.isdigit():
                selected_dep_id = int(dep_value)
            else:
                selected_dep_id = next(
                    (d["dep_id"] for d in departments if d["dep_name"] == dep_value),
                    None
                )

            
            if department_id:
                
                cursor.execute("UPDATE student_department SET dep_id=%s WHERE s_id=%s",
                               (selected_dep_id, username))
            else:

                
                cursor.execute("INSERT INTO student_department (s_id, dep_id) VALUES (%s, %s)",
                               (username, selected_dep_id))

            db.commit()

            # refresh with new department name
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT dep_id, dep_name FROM departments WHERE dep_id=%s", (selected_dep_id,))
            record = cursor.fetchone()
            cursor.fetchall()  
            department_id = record["dep_id"]
            department_name = record["dep_name"]
            editable = False

    
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT name, column_name FROM helper_student_studied_courses")
    courses = cursor.fetchall()

    # fetch student courses table
    cursor.execute("SELECT * FROM student_studied_courses WHERE student_id=%s", (username,))
    student_courses = cursor.fetchall()
    
    # print(student_courses)

    
    not_studied = []
    gpa = ''
    if student_courses:

        for lis in student_courses:

            for course in courses:
                col_name = course["column_name"]
                if lis[col_name] == "0" or lis[col_name] != "0":   # check dynamically
                    not_studied.append({
                        "name": course["name"],
                        "column_name": col_name
                    })

            break
    else:
        not_studied = courses

    # map semester → courses
    semester_courses = {}
    if student_courses:

        print(student_courses)
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT gpa FROM student_gpa WHERE s_id=%s ", (username,))
        db_gpa = cursor.fetchone()
        cursor.fetchall()  

        gpa = db_gpa['gpa']

        for lis in student_courses:
        
            for col, value in lis.items():
                if col != "student_id" and col !="sem_id" and value != "0":
                            
                    dashed_parts = value.split(',')
                    # print('meo')
                    # print(dashed_parts)

                    credit,grade = dashed_parts
                    semester = lis['sem_id']

                    # get course name
                    cursor = db.cursor(dictionary=True)
                    cursor.execute("SELECT name FROM helper_student_studied_courses WHERE column_name=%s", (col,))
                    result = cursor.fetchone()
                    cursor.fetchall()  
                    course_name = result["name"] if result else col

                    if semester not in semester_courses:
                        semester_courses[semester] = []
                    semester_courses[semester].append({
                        "course": course_name,
                        "credit": credit,
                        "grade": grade
                    })

        for key in semester_courses:
            cursor.execute(
                "SELECT * FROM student_sgpa WHERE s_id=%s AND sem_id=%s",
                (username, key)
            )
            result = cursor.fetchone()
            cursor.fetchall()  

            if result:
                
                semester_courses[key].append(result['s_gpa'])



    return render_template(
        "profile.html",
        username=username,
        department=department_name,
        departments=departments,
        editable=editable,
        semester_ids=semester_ids,
        courses=not_studied,
        semester_courses=semester_courses,
        cgpa = gpa
    )


@app.route("/add_semester/<username>", methods=["POST"])
@login_required
def add_semester(username):

    if username != session.get("username"):
        return redirect(url_for("index"))
    semester_id = request.form["semester_id"]

    edit_mode = request.form.get("edit_mode")  
    edit_semester_id = request.form.get("edit_semester_id")  # semester id if editing

    print('edit mode :- ',edit_mode)

    

    if edit_mode == 'false':
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM student_studied_courses WHERE student_id=%s and sem_id=%s", (username,semester_id))
        student_courses = cursor.fetchone()
        cursor.fetchall()  

        if student_courses:

            print(student_courses)

            flash(f"Semester {semester_id} is already added for this student!", "error")
            return redirect(url_for("profile", username=username))
    
        
    main_data_list = []
    upper_calculations = 0.00
    lower_calculation = 0.00
    for i in range(10):
        inner_list = []
        course_col = request.form.get(f"course_{i}")  # column name
        print(course_col)
        if course_col:
            # print('meo')
            # print(course_col)
            credit = request.form.get(f"credit_{i}")
            grade = request.form.get(f"grade_{i}")
            inner_list.append(course_col)
            inner_list.append(credit)
            inner_list.append(grade)
            main_data_list.append(inner_list)
            upper_calculations = upper_calculations + float(credit) * grade_points(grade)
            # print(upper_calculations)
            lower_calculation = lower_calculation + float(credit)
            # print(lower_calculation)
    
    final_sgpa = round(upper_calculations/lower_calculation,2)

    if final_sgpa:
        
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM student_gpa WHERE s_id=%s", (username,))
        student_cgpa = cursor.fetchone()
        cursor.fetchall()  

        old_lower = 0.00
        old_upper = 0.00
        cgpa = 0.00
        if(student_cgpa):
            old_upper = float(student_cgpa['upper_part'])
            old_lower = int(student_cgpa['lower_part'])
            cgpa = float(student_cgpa['gpa'])
        


        old_old_lower = 0.00
        old_old_upper = 0.00
        if edit_mode == 'true':
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM student_studied_courses WHERE student_id=%s and sem_id=%s", (username,semester_id))
            student_courses = cursor.fetchone()
            cursor.fetchall()  
            for key,value in student_courses.items():
                if value != '0' and key != 'student_id' and key != 'sem_id':
                    credits,grade = value.split(',')
                    credits = int(credits)
                    grade = grade_points(grade)
                    old_old_upper += credits * grade
                    old_old_lower+=credits

            print("old upper",old_upper)
            print("old lower",old_lower)

            old_lower = old_lower - old_old_lower
            old_upper = old_upper - old_old_upper

            print("old upper",old_upper)
            print("old lower",old_lower)


            old_lower += lower_calculation
            old_upper+= upper_calculations

            print("upper_calculations",upper_calculations)
            print("lower_calculation",lower_calculation)

            print("old upper",old_upper)
            print("old lower",old_lower)
            cgpa = round(old_upper/old_lower,2)

            print(cgpa,"insode the edit mode")

            query = f"""
                UPDATE student_gpa
                SET gpa = %s , upper_part = %s , lower_part = %s
                WHERE  s_id = %s
            """
            cursor.execute(query, (cgpa, old_upper, old_lower,username))
        else:
            if(student_cgpa):

                print('update query working ')

                old_lower += lower_calculation
                old_upper+= upper_calculations
                cgpa = round(old_upper/old_lower,2)

                query = f"""
                UPDATE student_gpa
                SET gpa = %s , upper_part = %s , lower_part = %s
                WHERE  s_id = %s
            """
                cursor.execute(query, (cgpa, old_upper, old_lower,username))

                
            else:
                old_lower += lower_calculation
                old_upper+= upper_calculations
                cgpa = round(old_upper/old_lower,2)

                query = """
                    INSERT INTO student_gpa (gpa, upper_part, lower_part, s_id)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (cgpa, old_upper, old_lower, username))
                db.commit()

        for row in main_data_list:
            course_col = row[0]
            credit = row[1]
            grade = row[2]

            if course_col:  # only if a course is selected
                value = f"{credit},{grade}"

                if edit_mode == 'true':
                    print(course_col)
                    query = f"""
                        UPDATE student_studied_courses
                        SET `{course_col}` = %s
                        WHERE sem_id = %s AND student_id = %s
                    """
                    cursor.execute(query, (value, semester_id, username))
                else:
                    cursor = db.cursor(dictionary=True)


                    # Step 1: check if record exists
                    check_query = """
                        SELECT 1 FROM student_studied_courses 
                        WHERE student_id = %s AND sem_id = %s
                        LIMIT 1
                    """
                    cursor.execute(check_query, (username, semester_id))
                    exists = cursor.fetchone()
                    cursor.fetchall()  

                    # Step 2: insert based on condition
                    if exists:
                        # print(exists)
                        query = f"""
                            UPDATE student_studied_courses
                            SET `{course_col}` = %s
                            WHERE sem_id = %s AND student_id = %s
                        """
                        cursor.execute(query, (value, semester_id, username))
                    else:
                        query = f"""
                            INSERT INTO student_studied_courses (`{course_col}`, student_id, sem_id)
                            VALUES (%s, %s, %s)
                        """
                        cursor.execute(query, (value, username, semester_id))


        if edit_mode == 'true':
            cursor = db.cursor(dictionary=True)
            query = f"""
                UPDATE student_sgpa
                SET s_gpa = %s
                WHERE sem_id = %s AND s_id = %s
            """
            cursor.execute(query, (final_sgpa, semester_id, username))

        else:
            cursor.execute("INSERT INTO student_sgpa (s_id, sem_id,s_gpa) VALUES (%s, %s,%s)", (username,semester_id,final_sgpa))
        db.commit()
    



    db.commit()
    return redirect(url_for("profile", username=username))



@app.route("/delete_semester", methods=["POST"])
@login_required
def delete_semester():
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    username = data.get("username")
    sem_id = data.get("sem")

    if username != session.get("username"):
        return redirect(url_for("index"))

    print(username,sem_id)

    try:
        

        cursor.execute("SELECT * FROM student_gpa WHERE s_id=%s", (username,))
        student_cgpa = cursor.fetchone()
        cursor.fetchall()  

        old_lower = 0.00
        old_upper = 0.00
        cgpa = 0.00
        if(student_cgpa):
            old_upper = float(student_cgpa['upper_part'])
            old_lower = int(student_cgpa['lower_part'])
            cgpa = float(student_cgpa['gpa'])

        old_old_lower = 0.00
        old_old_upper = 0.00
        cursor.execute("SELECT * FROM student_studied_courses WHERE student_id=%s and sem_id=%s", (username,sem_id))
        student_courses = cursor.fetchone()
        cursor.fetchall()  
        for key,value in student_courses.items():
            if value != '0' and key != 'student_id' and key != 'sem_id':
                credits,grade = value.split(',')
                credits = int(credits)
                grade = grade_points(grade)
                old_old_upper += credits * grade
                old_old_lower+=credits

        old_lower = old_lower - old_old_lower
        old_upper = old_upper - old_old_upper
        
        if old_lower == 0:
            cgpa = 0.00
        else:
            cgpa = round(old_upper/old_lower,2)
            
        query = f"""
            UPDATE student_gpa
            SET gpa = %s , upper_part = %s , lower_part = %s
            WHERE  s_id = %s
        """
        cursor.execute(query, (cgpa, old_upper, old_lower,username))

        

        # Delete from student_studied_courses
        cursor.execute(
            "DELETE FROM student_studied_courses WHERE student_id = %s AND sem_id = %s",
            (username, sem_id)
        )

        # Also delete from student_sgpa (if exists)
        cursor.execute(
            "DELETE FROM student_sgpa WHERE s_id = %s AND sem_id = %s",
            (username, sem_id)
        )

        db.commit()
        success = True
    except Exception as e:
        db.rollback()
        print("Error deleting:", e)
        success = False

    return jsonify({"success": success})


@app.route("/add_drop_courses")
def add_drop_courses():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT name, column_name FROM helper_student_studied_courses")
    courses = cursor.fetchall()   # this will be a list of dicts since you use dictionary cursor

    return render_template("add_drop.html", courses=courses)


@app.route("/launch_selection")
@login_required
def launch_courses():
    cursor = db.cursor(dictionary=True)
    try:
        # Compute current semester (Python logic)
        now = datetime.now()
        month = now.month
        year = now.year

        if 1 <= month <= 5:
            current_semester = f"Spring {year}"
        elif 6 <= month <= 7:
            current_semester = f"Summer {year}"
        else:
            current_semester = f"Fall {year}"

        # Ensure current semester exists in DB (optional safety)
        cursor.execute("SELECT semester_id FROM semester_id_data WHERE semester_id = %s", (current_semester,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (current_semester,))
            db.commit()

        # Latest launch info
        cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return render_template("launch_selection.html", mode="setup", semester=current_semester)

        start_time = row["launch_datetime"]
        end_time = row["result_datetime"]
        now = datetime.now()

        if now < end_time:
            return render_template(
                "launch_selection.html",
                mode="countdown",
                launch_time=start_time,
                result_time=end_time,
                semester=current_semester
            )
        else:
            return render_template("launch_selection.html", mode="expired", semester=current_semester)

    except Exception as e:
        print("Error loading launch selection:", e)
        return "Error loading launch selection", 500
    
@app.route("/launch_selection_TA")
@login_required
def launch_courses_TA():
    cursor = db.cursor(dictionary=True)
    try:
        # Compute current semester (Python logic)
        now = datetime.now()
        month = now.month
        year = now.year

        if 1 <= month <= 5:
            current_semester = f"Spring {year}"
        elif 6 <= month <= 7:
            current_semester = f"Summer {year}"
        else:
            current_semester = f"Fall {year}"

        # Ensure current semester exists in DB (optional safety)
        cursor.execute("SELECT semester_id FROM semester_id_data WHERE semester_id = %s", (current_semester,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (current_semester,))
            db.commit()

        # Latest launch info
        cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return render_template("launch_selection_TA.html", mode="setup", semester=current_semester)

        start_time = row["launch_datetime"]
        end_time = row["result_datetime"]
        now = datetime.now()

        if now < end_time:
            return render_template(
                "launch_selection_TA.html",
                mode="countdown",
                launch_time=start_time,
                result_time=end_time,
                semester=current_semester
            )
        else:
            return render_template("launch_selection_TA.html", mode="expired", semester=current_semester)

    except Exception as e:
        print("Error loading launch selection:", e)
        return "Error loading launch selection", 500





@app.route("/update_course", methods=["POST"])
@login_required
def update_course():
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    old_course_name = data.get("old_course_name")
    new_course_name = data.get("new_course_name")
    old_column_name = data.get("old_column_name")
    new_column_name = data.get("new_column_name")

    print("Old Course Name:", old_course_name)
    print("New Course Name:", new_course_name)
    print("Old Column Name:", old_column_name)
    print("New Column Name:", new_column_name)

    try:
        # ✅ Check if new column already exists in student_studied_courses
        cursor.execute("SHOW COLUMNS FROM student_studied_courses LIKE %s", (new_column_name,))
        column_exists = cursor.fetchone()

        if column_exists:
            return jsonify({
                "success": False,
                "message": f"Column '{new_column_name}' already exists! Please choose a different name."
            })

        # 1️⃣ Rename column in student_studied_courses
        alter_query = f"""
            ALTER TABLE student_studied_courses 
            CHANGE {old_column_name} {new_column_name} VARCHAR(50) DEFAULT '0'
        """
        cursor.execute(alter_query)

        # 2️⃣ Rename in the corresponding display table
        if old_column_name.split('_')[-1] == 'lab':
            alter_query = f"""
                ALTER TABLE ld_courses_display 
                CHANGE {old_column_name} {new_column_name} INT DEFAULT 0
            """
        else:
            alter_query = f"""
                ALTER TABLE TA_courses_display 
                CHANGE {old_column_name} {new_column_name} INT DEFAULT 0
            """
        cursor.execute(alter_query)

        # 3️⃣ Update helper_student_studied_courses
        update_helper_query = """
            UPDATE helper_student_studied_courses
            SET name = %s, column_name = %s
            WHERE name = %s AND column_name = %s
        """
        cursor.execute(update_helper_query, (new_course_name, new_column_name, old_course_name, old_column_name))

        db.commit()

        return jsonify({"success": True, "message": "Course updated successfully!"})

    except Exception as e:
        db.rollback()
        print("Error while updating:", str(e))
        return jsonify({"success": False, "message": f"Error: {str(e)}"})



@app.route("/delete_course", methods=["POST"])
@login_required
def delete_course():
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    course_name = data.get("course_name")
    column_name = data.get("column_name")

    print("Deleting Course:", course_name)
    print("Deleting Column:", column_name)

    try:
        # 1️⃣ Delete column from student_studied_courses
        alter_query = f"ALTER TABLE student_studied_courses DROP COLUMN {column_name}"
        cursor.execute(alter_query)

        # ✅ Add same column to corresponding table
        if column_name.split('_')[-1] == 'lab':
            alter_query = f"ALTER TABLE ld_courses_display DROP COLUMN {column_name}"
        else:
            alter_query = f"ALTER TABLE TA_courses_display DROP COLUMN {column_name}"
        cursor.execute(alter_query)

        # 2️⃣ Delete row from helper_student_studied_courses
        delete_helper_query = """
            DELETE FROM helper_student_studied_courses
            WHERE name = %s AND column_name = %s
        """
        cursor.execute(delete_helper_query, (course_name, column_name))

        db.commit()
        return jsonify({"success": True, "message": "Course deleted successfully!"})

    except Exception as e:
        db.rollback()
        print("Error while deleting:", str(e))
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@app.route("/add_course", methods=["POST"])
@login_required
def add_course():
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    course_name = data.get("course_name")
    column_name = data.get("column_name")

    print("Adding Course:", course_name)
    print("Adding Column:", column_name)

    try:
        # 🔹 Check if column already exists in student_studied_courses
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'student_studied_courses' AND COLUMN_NAME = %s
        """, (column_name,))
        existing_column = cursor.fetchone()

        if existing_column:
            return jsonify({
                "success": False,
                "message": f"Column '{column_name}' already exists in student_studied_courses."
            }), 400

        # 🔹 Check if course already exists in helper_student_studied_courses
        cursor.execute("""
            SELECT * FROM helper_student_studied_courses 
            WHERE column_name = %s OR name = %s
        """, (column_name, course_name))
        existing_course = cursor.fetchone()

        if existing_course:
            return jsonify({
                "success": False,
                "message": f"Course '{course_name}' or column '{column_name}' already exists in helper_student_studied_courses."
            }), 400

        # ✅ Add new column to student_studied_courses
        alter_query = f"ALTER TABLE student_studied_courses ADD COLUMN {column_name} VARCHAR(50) DEFAULT '0'"
        cursor.execute(alter_query)

        # ✅ Add same column to corresponding table
        if column_name.split('_')[-1] == 'lab':
            alter_query = f"ALTER TABLE ld_courses_display ADD COLUMN {column_name} INT DEFAULT '0'"
        else:
            alter_query = f"ALTER TABLE TA_courses_display ADD COLUMN {column_name} INT DEFAULT '0'"
        cursor.execute(alter_query)

        # ✅ Insert into helper table
        insert_helper_query = """
            INSERT INTO helper_student_studied_courses (name, column_name)
            VALUES (%s, %s)
        """
        cursor.execute(insert_helper_query, (course_name, column_name))
        db.commit()

        return jsonify({"success": True, "message": "✅ Course added successfully!"})

    except Exception as e:
        db.rollback()
        print("Error while adding course:", str(e))
        return jsonify({"success": False, "message": f"❌ Error: {str(e)}"}), 500




from datetime import datetime

@app.route("/set_launch", methods=["POST"])
@login_required
def set_launch():
    cursor = db.cursor(dictionary=True)
    data = request.get_json() or {}
    launch_str = data.get("launch")
    result_str = data.get("result")
    semester = data.get("semester")

    if not launch_str or not result_str:
        return jsonify({"success": False, "message": "Missing launch or result datetime"}), 400

    try:
        launch_dt = datetime.strptime(launch_str, "%Y-%m-%d %H:%M:%S")
        result_dt = datetime.strptime(result_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        return jsonify({"success": False, "message": f"Invalid datetime format: {e}"}), 400

    if result_dt <= launch_dt:
        return jsonify({"success": False, "message": "Result datetime must be after launch datetime."}), 400

    try:
        print('inserting the new launch')
        cursor = db.cursor(dictionary=True)
        # Insert new launch
        insert_q = """
            INSERT INTO launch_selection (launch_datetime, result_datetime,semester_id)
            VALUES (%s, %s,%s)
        """
        cursor.execute(insert_q, (launch_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                  result_dt.strftime("%Y-%m-%d %H:%M:%S"),semester))
        


        db.commit()
        
        cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        launch_id = row['id']
        db.commit()
        cursor.close()

        # Schedule the result calculation
        schedule_result_job(launch_id, result_dt)

        return jsonify({"success": True, "id": launch_id, "message": "Launch saved and scheduler set."})
    except Exception as e:
        db.rollback()
        print("Error in /set_launch:", e)
        return jsonify({"success": False, "message": f"DB error: {str(e)}"}), 500


@app.route("/set_launch_TA", methods=["POST"])
@login_required
def set_launch_TA():
    cursor = db.cursor(dictionary=True)
    data = request.get_json() or {}
    launch_str = data.get("launch")
    result_str = data.get("result")
    semester = data.get("semester")

    if not launch_str or not result_str:
        return jsonify({"success": False, "message": "Missing launch or result datetime"}), 400

    try:
        launch_dt = datetime.strptime(launch_str, "%Y-%m-%d %H:%M:%S")
        result_dt = datetime.strptime(result_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        return jsonify({"success": False, "message": f"Invalid datetime format: {e}"}), 400

    if result_dt <= launch_dt:
        return jsonify({"success": False, "message": "Result datetime must be after launch datetime."}), 400

    try:
        print('inserting the new launch')
        cursor = db.cursor(dictionary=True)
        # Insert new launch
        insert_q = """
            INSERT INTO launch_selection_TA (launch_datetime, result_datetime,semester_id)
            VALUES (%s, %s,%s)
        """
        cursor.execute(insert_q, (launch_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                  result_dt.strftime("%Y-%m-%d %H:%M:%S"),semester))
        
        db.commit()

        cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        launch_id = row['id']
        db.commit()
        cursor.close()

        # Schedule the result calculation
        schedule_result_job_TA(launch_id, result_dt)

        return jsonify({"success": True, "id": launch_id, "message": "Launch saved and scheduler set."})
    except Exception as e:
        db.rollback()
        print("Error in /set_launch_TA:", e)
        return jsonify({"success": False, "message": f"DB error: {str(e)}"}), 500


@app.route("/delete_launch", methods=["POST"])
@login_required
def delete_launch():
    try:
        cursor = db.cursor(dictionary=True)

        data = request.get_json() or {}
        semester = data.get("semester")

        # Get latest launch id
        cursor.execute("SELECT MAX(id) as max_id FROM launch_selection")
        result = cursor.fetchone()
        if not result or not result["max_id"]:
            cursor.close()
            return jsonify({"success": False, "message": "No launch found."})

        latest_id = result["max_id"]

        # Delete from launch_selection
        cursor.execute("DELETE FROM launch_selection WHERE id = %s", (latest_id,))
        # Delete from student_applications
        cursor.execute("DELETE FROM student_applications WHERE launch_id = %s", (latest_id,))

        # cursor.execute("DELETE FROM ld_courses_display WHERE sem_id = %s", (semester,))


        db.commit()
        cursor.close()

        # Remove scheduled job if exists
        try:
            scheduler.remove_job(CURRENT_JOB_ID)
        except Exception:
            pass

        return jsonify({"success": True, "message": "Launch deleted and scheduler removed."})

    except Exception as e:
        print("Error deleting:", e)
        return jsonify({"success": False, "message": str(e)})


@app.route("/delete_launch_TA", methods=["POST"])
@login_required
def delete_launch_TA():
    try:

        print('working')
        cursor = db.cursor(dictionary=True)

        data = request.get_json() or {}
        semester = data.get("semester")

        # Get latest launch id
        cursor.execute("SELECT MAX(id) as max_id FROM launch_selection_TA")
        result = cursor.fetchone()
        if not result or not result["max_id"]:
            cursor.close()
            return jsonify({"success": False, "message": "No launch found."})

        latest_id = result["max_id"]

        # Delete from launch_selection
        cursor.execute("DELETE FROM launch_selection_TA WHERE id = %s", (latest_id,))
        # Delete from student_applications
        cursor.execute("DELETE FROM student_applications_TA WHERE launch_id = %s", (latest_id,))

        # cursor.execute("DELETE FROM ld_courses_display WHERE sem_id = %s", (semester,))


        db.commit()
        cursor.close()

        # Remove scheduled job if exists
        try:
            scheduler.remove_job(CURRENT_JOB_ID)
        except Exception:
            pass

        return jsonify({"success": True, "message": "Launch deleted and scheduler removed."})

    except Exception as e:
        print("Error deleting:", e)
        return jsonify({"success": False, "message": str(e)})


@app.route("/apply_course", methods=["POST"])
@login_required
def apply_course():
    cursor = db.cursor(dictionary=True)
    try:
        data = request.form
        username = data.get("username")
        course_code = data.get("course_code")   # match HTML
        
        section = data.get("section")
        if username != session.get("username"):
            return redirect(url_for("index"))

        print(username,course_code,section)

        # Validate inputs
        if not username or not course_code or not section:
            print('apply _course is working after ')
            return redirect(url_for("student_apply", username=username or ""))
        
        print('eror')
        print('apply _course is working after ')

        cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row or not row["id"]:
            return redirect(url_for("student_apply", username=username))
        
        

        launch_id = row["id"]
        time_apply = datetime.now()
        print("checl this out ",launch_id)

        # --- INTERVIEW INHERITANCE ---
        cursor.execute("""
            SELECT interview_marks, submission_files_path FROM student_applications 
            WHERE username = %s AND course_code = %s AND launch_id = %s AND interview_taken = 1 
            LIMIT 1
        """, (username, course_code, launch_id))
        existing_int = cursor.fetchone()
        
        int_taken = 1 if existing_int else 0
        int_marks = existing_int['interview_marks'] if existing_int else 0
        file_path = existing_int['submission_files_path'] if existing_int else None

        cursor.execute("""
            INSERT INTO student_applications
            (username, course_code, launch_id, time_apply, semester_id, section, interview_taken, interview_marks, submission_files_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, course_code, launch_id, time_apply, row['semester_id'], section, int_taken, int_marks, file_path))

        db.commit()

        print('apply _course is working at the end ', launch_id)

        # Exam is now integrated — just return JSON, no subprocess needed
        if int_taken == 0:
            return jsonify({'success': True, 'needs_exam': True})
        else:
            return jsonify({'success': True, 'needs_exam': False})

    except Exception as e:
        db.rollback()
        print("Error applying for course:", e)
        return redirect(url_for("student_apply", username=username))

@app.route("/get_departments")
def get_departments():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT dep_id, dep_name FROM departments")
    departments = cursor.fetchall()
    return jsonify({"success": True, "departments": departments})


@app.route("/apply_course_TA", methods=["POST"])
@login_required
def apply_course_TA():
    print('reached the end point ?')
    cursor = db.cursor(dictionary=True)
    try:

        print('checking working or not')
        data = request.form
        username = data.get("username")
        course_code = data.get("course_code")   # match HTML
        
        section = data.get("section")
        if username != session.get("username"):
            return redirect(url_for("index"))

        print(username,course_code,section)

        # Validate inputs
        if not username or not course_code or not section:
            print('apply _course is working after ')
            return redirect(url_for("student_apply_TA", username=username or ""))
        
        print('apply _course is working after ')

        cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row or not row["id"]:
            return redirect(url_for("student_apply_TA", username=username))
        
        launch_id = row["id"]
        time_apply = datetime.now()

        # --- INTERVIEW INHERITANCE ---
        cursor.execute("""
            SELECT interview_marks, submission_files_path FROM student_applications_TA 
            WHERE username = %s AND course_code = %s AND launch_id = %s AND interview_taken = 1 
            LIMIT 1
        """, (username, course_code, launch_id))
        existing_int = cursor.fetchone()
        
        int_taken = 1 if existing_int else 0
        int_marks = existing_int['interview_marks'] if existing_int else 0
        file_path = existing_int['submission_files_path'] if existing_int else None

        cursor.execute("""
            INSERT INTO student_applications_TA 
            (username, course_code, section, launch_id, time_apply, semester_id, interview_taken, interview_marks, submission_files_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, course_code, section, launch_id, time_apply, row['semester_id'], int_taken, int_marks, file_path))
        db.commit()

        print('apply _course is working at the end ')

        # Exam is now integrated — just return JSON, no subprocess needed
        if int_taken == 0:
            return jsonify({'success': True, 'needs_exam': True})
        else:
            return jsonify({'success': True, 'needs_exam': False})

    except Exception as e:
        db.rollback()
        print("Error applying for course:", e)
        return redirect(url_for("student_apply_TA", username=username))

# Handle deletion
@app.route("/delete_course_apply", methods=["POST"])
@login_required
def delete_course_apply():
    cursor = db.cursor(dictionary=True)
    try:
        username = request.form.get("username")
        course_code = request.form.get("course_code")
        # dep_name = request.form.get("dep_id")   # department name
        section = request.form.get("section")
        if username != session.get("username"):
            return redirect(url_for("index"))

        if not all([username, course_code, section]):
            return "Missing required data", 400
        
        print('working')

        now = datetime.now()
        month = now.month
        year = now.year
        if 1 <= month <= 5:
            semester_id = f"Spring {year}"
        elif 6 <= month <= 7:
            semester_id = f"Summer {year}"
        else:
            semester_id = f"Fall {year}"

        # Get latest launch_id
        cursor.execute("SELECT MAX(id) AS launch_id FROM launch_selection")
        row = cursor.fetchone()
        if not row or not row["launch_id"]:
            return "No active launch found", 400
        launch_id = row["launch_id"]

        # Check total applications for this course to prevent deleting the last one
        cursor.execute("""
            SELECT COUNT(*) AS total FROM student_applications
            WHERE username = %s AND course_code = %s AND launch_id = %s
        """, (username, course_code, launch_id))
        count_row = cursor.fetchone()
        if count_row and count_row["total"] <= 1:
            return redirect(url_for("student_apply", username=username))

        # Delete the application
        cursor.execute("""
            DELETE FROM student_applications
            WHERE username = %s AND launch_id = %s AND semester_id = %s
                   AND TRIM(section) = %s AND course_code = %s
        """, (username, launch_id, semester_id, section, course_code))
        db.commit()

        # Redirect back to the page
        return redirect(url_for("student_apply", username=username))

    except Exception as e:
        db.rollback()
        print("Error deleting course:", e)
        return "Error deleting application", 500

# Handle deletion
@app.route("/delete_course_apply_TA", methods=["POST"])
@login_required
def delete_course_apply_TA():
    cursor = db.cursor(dictionary=True)
    try:
        username = request.form.get("username")
        course_code = request.form.get("course_code")
        section = request.form.get("section")
        if username != session.get("username"):
            return redirect(url_for("index"))

        cursor = db.cursor(dictionary=True)

        # Get latest launch_id
        cursor.execute("SELECT MAX(id) AS launch_id FROM launch_selection_TA")
        row = cursor.fetchone()
        cursor.fetchall()
        if not row or not row["launch_id"]:
            return "No active launch found", 400
        launch_id = row["launch_id"]

        # Check total applications for this course to prevent deleting the last one
        cursor.execute("""
            SELECT COUNT(*) AS total FROM student_applications_TA
            WHERE username = %s AND course_code = %s AND launch_id = %s
        """, (username, course_code, launch_id))
        count_row = cursor.fetchone()
        if count_row and count_row["total"] <= 1:
            return redirect(url_for("student_apply_TA", username=username))

        # Delete application
        cursor.execute("""
            DELETE FROM student_applications_TA
            WHERE username = %s AND course_code = %s AND launch_id = %s AND TRIM(section) = %s
        """, (username, course_code, launch_id, section))
        db.commit()

        return redirect(url_for("student_apply_TA", username=username))
    except Exception as e:
        print("Error deleting course:", e)
        return "Error deleting application", 500

@login_required
@app.route("/apply/<username>")
def student_apply(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)
    try:
        # ✅ Check latest launch
        cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        if not row:
            return render_template("student_apply.html", username=username, courses=[], message="No launch available.")

        start_time, end_time, semester = row['launch_datetime'], row['result_datetime'], row['semester_id']
        launch_id = row['id']

        # ✅ Validate time window
        if not (start_time <= datetime.now() <= end_time):
            return render_template("student_apply.html", username=username, courses=[], message="Course application is currently unavailable.")

        # ✅ Check LD limit
        cursor.execute("SELECT counter FROM student_ld_counter WHERE sem_id=%s AND s_id=%s", (semester, username))
        row = cursor.fetchone()
        ld_counter = 0
        if row and row['counter'] == 2:
            ld_counter = row['counter']
            return render_template("student_apply.html", username=username, courses=[], message="You are already LD for two courses.")

        cursor.fetchall()

        # ✅ Check LD limit
        cursor.execute("SELECT counter FROM student_TA_counter WHERE sem_id=%s AND s_id=%s", (semester, username))
        row = cursor.fetchone()
        TA_counter = 0
        if row and row['counter'] == 2:
            TA_counter = row['counter']
            return render_template("student_apply.html", username=username, courses=[], message="You are already TA for two courses.")

        cursor.fetchall()

        if ld_counter == 1 and TA_counter == 1 :
            return render_template("student_apply.html", username=username, courses=[], message="You are already TA for one course and LD for one course")


        # ✅ Student studied courses
        cursor.execute("SELECT * FROM student_studied_courses WHERE student_id = %s", (username,))
        student_row_courses = cursor.fetchall()
        if not student_row_courses:
            return render_template("student_apply.html", username=username, courses=[], message="No studied courses found.")


        studied_courses = []
        for student_row in student_row_courses:
            for key, value in student_row.items():
                if key not in ("student_id", "sem_id") and value != '0':
                    if key.split('_')[-1].lower() == 'lab' or key == 'Introduction_to_Information_and_Communication_Technologies':
                        studied_courses.append(key)

        final_courses = []
        if studied_courses:
            for l in studied_courses:
                cursor.execute("""
                    SELECT DISTINCT lab_name, section 
                    FROM lab_allocations 
                    WHERE column_name = %s AND allocation_count = 0
                """, (l,))
                courses = cursor.fetchall()

                
                lab_name = None

                sections = []
                for row in courses:
                    lab_name = row['lab_name']

                   

                    cursor.execute("""
                        SELECT * FROM student_applications
                        WHERE username = %s AND launch_id = %s AND semester_id =%s and TRIM(section) = %s and course_code =%s
                    """, (username, launch_id,semester,row['section'].strip(),l))
                    applied_rows = cursor.fetchall()
                    # print(applied_rows)
                    if applied_rows:
                        print('yes',applied_rows)
                        print()
                        sections.append([row['section'],1])  # one tells that he has applied 
                    else:
                        sections.append([row['section'],0]) # zero tells that he has not applied


                # --- INTERVIEW LOGIC (LD) ---
                cursor.execute("""
                    SELECT interview_taken, interview_marks 
                    FROM student_applications
                    WHERE username = %s AND launch_id = %s AND course_code = %s AND interview_taken = 1
                    LIMIT 1
                """, (username, launch_id, l))
                existing_interview = cursor.fetchone()
                
                course_interview_taken = 1 if existing_interview else 0
                course_interview_marks = existing_interview['interview_marks'] if existing_interview else 0

                if sections:
                    final_courses.append({
                        'name': lab_name,
                        'column_name': l,
                        'sec_department': sections,
                        'interview_taken': course_interview_taken,
                        'interview_marks': course_interview_marks,
                        'role': 'ld'
                    })

            
            # over here i want to add the new functionality ok

           
            return render_template("student_apply.html", username=username, courses=final_courses, message=None)
        else:
            return render_template("student_apply.html", username=username, courses=[], message="No studied courses found.")

    except Exception as e:
        print("Error fetching courses:", e)
        return "Error loading courses", 500

# Show the apply page when the TA
@app.route("/apply_TA/<username>")
@login_required
def student_apply_TA(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM departments")
        departments = cursor.fetchall()
        sections = [chr(i) for i in range(65, 91)]

        # Step 0: Check latest launch
        cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.fetchall()

        if not row:
            return render_template("student_apply_TA.html", username=username, courses=[], message="No launch is available at the moment.")

        start_time = row['launch_datetime']
        end_time = row['result_datetime']
        semester = row['semester_id']

        if not (start_time <= datetime.now() <= end_time):
            return render_template("student_apply_TA.html", username=username, courses=[], message="Course application is currently unavailable.")
        

        # ✅ Check LD limit
        cursor.execute("SELECT counter FROM student_ld_counter WHERE sem_id=%s AND s_id=%s", (semester, username))
        row = cursor.fetchone()
        ld_counter = 0
        if row and row['counter'] == 2:
            ld_counter = row['counter']
            return render_template("student_apply_TA.html", username=username, courses=[], message="You are already LD for two courses.")

        cursor.fetchall()

        # ✅ Check LD limit
        cursor.execute("SELECT counter FROM student_TA_counter WHERE sem_id=%s AND s_id=%s", (semester, username))
        row = cursor.fetchone()
        TA_counter = 0
        if row and row['counter'] == 2:
            TA_counter = row['counter']
            return render_template("student_apply_TA.html", username=username, courses=[], message="You are already TA for two courses.")

        cursor.fetchall()

        if ld_counter == 1 and TA_counter == 1 :
            return render_template("student_apply_TA.html", username=username, courses=[], message="You are already TA for one course and LD for one course")


        cursor.execute("SELECT * FROM launch_selection_TA ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.fetchall()

        launch_id = row["id"]

        # Step 1: get student's studied courses
        cursor.execute("SELECT * FROM student_studied_courses WHERE student_id = %s", (username,))
        student_row_courses = cursor.fetchall()

        if not student_row_courses:
            return render_template("student_apply_TA.html", username=username, courses=[], message="No studied courses found for this student.")

        studied_courses = []
        for student_row in student_row_courses:
            for key, value in student_row.items():
                # print('apply key :- ',key,key.split('_')[-1].lower())


                if key not in ("student_id", "sem_id") and value != '0':
                    if key.split('_')[-1].lower() != 'lab':
                        studied_courses.append(key)

        print(studied_courses)
        cursor.execute("SELECT * from TA_courses_display WHERE sem_id = %s", (semester,))
        row = cursor.fetchone()
        print(row)

        final_courses = []
        if studied_courses:
            for l in studied_courses:
                cursor.execute("""
                    SELECT DISTINCT course_name, section 
                    FROM TA_allocations 
                    WHERE column_name = %s AND allocation_count = 0
                """, (l,))
                courses = cursor.fetchall()

                
                course_name = None

                sections = []
                for row in courses:
                    course_name = row['course_name']

                   

                    cursor.execute("""
                        SELECT * FROM student_applications_TA
                        WHERE username = %s AND launch_id = %s AND semester_id =%s and TRIM(section) = %s and course_code =%s
                    """, (username, launch_id,semester,row['section'].strip(),l))
                    applied_rows = cursor.fetchall()
                    # print(applied_rows)
                    if applied_rows:
                        print('yes',applied_rows)
                        print()
                        sections.append([row['section'],1])  # one tells that he has applied 
                    else:
                        sections.append([row['section'],0]) # zero tells that he has not applied


                # --- INTERVIEW LOGIC (TA) ---
                cursor.execute("""
                    SELECT interview_taken, interview_marks 
                    FROM student_applications_TA
                    WHERE username = %s AND launch_id = %s AND course_code = %s AND interview_taken = 1
                    LIMIT 1
                """, (username, launch_id, l))
                existing_interview = cursor.fetchone()
                
                course_interview_taken = 1 if existing_interview else 0
                course_interview_marks = existing_interview['interview_marks'] if existing_interview else 0

                if sections:
                    final_courses.append({
                        'name': course_name,
                        'column_name': l,
                        'sec_department': sections,
                        'interview_taken': course_interview_taken,
                        'interview_marks': course_interview_marks,
                        'role': 'ta'
                    })

            # print(final_courses)

           
            return render_template("student_apply_TA.html", username=username, courses=final_courses, message=None)
        else:
            return render_template("student_apply_TA.html", username=username, courses=[], message="No studied courses found.")


    except Exception as e:
        print("Error fetching courses:", e)
        return "Error loading courses", 500
    

from flask import flash

@app.route("/view_ld_results/<username>")
@login_required
def view_ld_results(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)

    # check the latest launch
    cursor.execute("SELECT * FROM ld_timeout_acceptance ORDER BY id DESC LIMIT 1")
    data = cursor.fetchone()

    if data:
        now = datetime.now()
        result_time = data['result_datetime']
        launch_time = data['launch_datetime']
        print(now)
        if launch_time < now < result_time:
            # determine current semester
            month = now.month
            year = now.year
            
            if 1 <= month <= 5:
                current_semester = f"Spring {year}"
            elif 6 <= month <= 7:
                current_semester = f"Summer {year}"
            else:
                current_semester = f"Fall {year}"

            cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
            data = cursor.fetchone()
            launch_id = data['id']

            # fetch LD results for this student + semester
            cursor.execute("""
                SELECT * FROM ld_finalization 
                WHERE sem_id = %s AND s_id = %s AND launch_id = %s
            """, (current_semester, username, launch_id))
            applied_rows = cursor.fetchall()

            ld_courses = {
                row['course_name']: {
                    "acceptance": row['acceptance'],
                    "section": row['section']
                }
                for row in applied_rows
            }


            print(ld_courses)

            if ld_courses:
                # map course column_name → friendly name
                cursor.execute("SELECT name, column_name FROM helper_student_studied_courses")
                courses = cursor.fetchall()

                # include is_selected flag if acceptance == 1
                selected_courses = []
                for row in courses:
                    col = row["column_name"]
                    if col in ld_courses:
                        selected_courses.append({
                            "name": row["name"],
                            "column_name": col,
                            "section": ld_courses[col]["section"],   # 👈 ADD SECTION HERE
                            "is_selected": (ld_courses[col]["acceptance"] == 1)
                        })


                print('printing the selected courses :- ', selected_courses)

                # flash success if student has LD courses
                flash("You have LD results available!", "success")

                return render_template(
                    "viewldresult.html",
                    username=username,
                    results=selected_courses
                )
            else:
                # flash warning if no LD courses selected
                flash("You have not been selected as LD for any course this semester.", "warning")
                return render_template("viewldresult.html", username=username, results=None)
            
        else:
            flash("Results are not yet available. Please wait until the result time.", "warning")
            return render_template("viewldresult.html", username=username, results=None)
        
    else:
        flash("Results are not yet available. Please wait until the result time.", "warning")
        return render_template("viewldresult.html", username=username, results=None)



@app.route("/submit_ld_selection/<username>", methods=["POST"])
@login_required
def submit_ld_selection(username):
    if username != session.get("username"):
        return redirect(url_for("index"))

    cursor = db.cursor(dictionary=True)


    # check the latest launch
    cursor.execute("SELECT * FROM ld_timeout_acceptance ORDER BY id DESC LIMIT 1")
    data = cursor.fetchone()

    if data:
        now = datetime.now()
        result_time = data['result_datetime']
        launch_time = data['launch_datetime']

        # if inside launch period → show a message or redirect
        if launch_time < now < result_time:
            

            all_courses_raw = request.form.to_dict(flat=False)  # get all values as lists

            course_status = {}

            for key, values in all_courses_raw.items():
                # key = 'courses[Data_Structures_Lab]'
                if key.startswith("courses[") and key.endswith("]"):
                    course_name = key[8:-1]  # strip 'courses[' and ']'
                    # values is a list like ['0', '1'] → take the last value (checkbox overrides hidden input)
                    course_status[course_name] = int(values[-1])

            print("Course status:", course_status)


        
    
            

            if not course_status:
                return "Error: No courses selected.", 400

            # print("Username:", username)
            # print("Selected column_names:", selected_courses , len(selected_courses))
            cursor = db.cursor(dictionary=True)

            # Determine current semester
            now = datetime.now()
            month = now.month
            year = now.year
            
            if 1 <= month <= 5:
                current_semester = f"Spring {year}"
            elif 6 <= month <= 7:
                current_semester = f"Summer {year}"
            else:
                current_semester = f"Fall {year}"

            # Get latest launch_id
            cursor.execute("SELECT * FROM launch_selection ORDER BY id DESC LIMIT 1")
            data = cursor.fetchone()
            launch_id = data['id']

            # ✅ Check LD limit
            cursor.execute("SELECT counter FROM student_ld_counter WHERE sem_id=%s AND s_id=%s", (current_semester, username))
            row = cursor.fetchone()
            ld_counter = 0
            if row and row['counter'] == 1:
                ld_counter = row['counter']

            # ✅ Check LD limit
            cursor.execute("SELECT counter FROM student_TA_counter WHERE sem_id=%s AND s_id=%s", (current_semester, username))
            row = cursor.fetchone()
            TA_counter = 0
            if row and row['counter'] == 1:
                TA_counter = row['counter']

            submission_sum = 0
            for course,value in course_status.items():
                submission_sum+=value

            if submission_sum == 2 and (TA_counter == 1 or ld_counter == 1):
                flash("You are already LD/TA of 1 course. You cannot select more than 1 course.", "warning")
                return redirect(url_for("view_ld_results", username=username))

            


            # Update acceptance for each selected course
            for course,value in course_status.items():

                if value == 1:

                    cursor.execute(
                        """
                        UPDATE ld_finalization 
                        SET acceptance = 1 
                        WHERE sem_id = %s AND s_id = %s AND course_name = %s AND launch_id = %s
                        """,
                        (current_semester, username, course, launch_id)
                    )
                else:

                    cursor.execute(
                        """
                        UPDATE ld_finalization 
                        SET acceptance = 0
                        WHERE sem_id = %s AND s_id = %s AND course_name = %s AND launch_id = %s
                        """,
                        (current_semester, username, course, launch_id)
                    )


            db.commit()  # don't forget to commit!

            flash("Your course selection has been submitted successfully.", "success")
            return redirect(url_for("view_ld_results", username=username))
        
        else:
            return "Results are not yet available. Please wait until the result time."
    else:
        return "Results are not yet available. Please wait until the result time."



@app.route("/view_results")
@login_required
def view_results():

    # Determine current semester
    now = datetime.now()
    month = now.month
    year = now.year

    if 1 <= month <= 5:   # Jan–May
        semester = f"Spring {year}"
    elif 6 <= month <= 7: # Jun–Jul
        semester = f"Summer {year}"
    else:                 # Aug–Dec
        semester = f"Fall {year}"

    # Read all rows from the lab_allocations table
    cursor = db.cursor(dictionary=True, buffered=True)
    
    cursor.execute("SELECT * FROM lab_allocations WHERE sem_id = %s", (semester,))
    data = cursor.fetchall()
    cursor.close()

    # Rename columns and prepare cleaned data
    results = []
    for row in data:
        results.append({
            "semester": row["sem_id"],
            "lab_name": row["lab_name"],
            "lab_instructor": row["lab_instructor"],
            "s_id_one": row["s_id_one"],
            "email_one": row["email_one"],
            "confirmed_one": row["confirmed_one"],
            "s_id_two": row["s_id_two"],
            "email_two": row["email_two"],
            "confirmed_two": row["confirmed_two"],
            "submission_files_path": row["submission_files_path"],
            "submission_files_path1": row["submission_files_path1"],
            "allocation_count": row["allocation_count"]
        })

    return render_template("admin_view_results.html", results=results)



@app.route("/go_home")
def go_home():
    return redirect(url_for("welcome_admin"))


import pandas as pd
import re

@app.route("/upload_labs")
@login_required
def upload_labs():
    return render_template("upload_labs.html")


@app.route("/upload_excel", methods=["POST"])
@login_required
def upload_excel():
    file = request.files.get("file")

    now = datetime.now()
    month = now.month
    year = now.year

    # ✅ Determine semester
    if 1 <= month <= 5:
        semester_id = f"Spring {year}"
    elif 6 <= month <= 7:
        semester_id = f"Summer {year}"
    else:
        semester_id = f"Fall {year}"

    cursor = db.cursor(dictionary=True)

    # ✅ Ensure semester exists
    cursor.execute("SELECT 1 FROM semester_id_data WHERE semester_id = %s", (semester_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (semester_id,))
        db.commit()
        print(f"Added new semester: {semester_id}")

    # ✅ Fetch existing courses
    cursor.execute("SELECT * FROM helper_student_studied_courses")
    student_courses = cursor.fetchall()
    courses_names = {r['name']: r['column_name'] for r in student_courses}

    if not file:
        return render_template("upload_labs.html", message="No file uploaded!")

    try:


        cursor.execute(f"SELECT * FROM teacher_login")
                     
        row = cursor.fetchall()



        intructor_names = []
        intructor_id = []

        
        if row:

            for r in row:
                intructor_names.append(r['name'])
                intructor_id.append(r['id'])
       

        names_and_id_diction = {}

        if row:
            for r in row:
                if r['name'] not in names_and_id_diction:
                    names_and_id_diction[r['name']] = r['id']

    
        # ✅ Read Excel file
        df = pd.read_excel(file, sheet_name='LDSheet', skiprows=2)
        df.columns = df.columns.str.strip()  # remove spaces around column names
        

        # Clean the course name: remove parentheses and text inside
        df['Lab Name'] = df['Lab Name'].str.replace(r'\(.*?\)', '', regex=True).str.strip()

        # Keep only relevant columns
        df = df[['Lab Name', 'Section', 'Strength', 'Lab Instructor']]

        # Optional: reset index
        df = df.reset_index(drop=True)

        # ✅ Safe column name generator
        def make_safe_column(name):
            print(name,' before')
            name = name.replace(' ', '_').replace('-', '_').replace('&','and').replace('___Repeat','')
            print(name,' after')
            
            return name

        # ✅ Insert each row
        for _, row in df.iterrows():
            print(row)
            safe_col = make_safe_column(row['Lab Name'])

            # Add to student_studied_courses if new
            if row['Lab Name'] not in courses_names:
                # ✅ Check if column exists in student_studied_courses
                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'student_studied_courses'
                    AND COLUMN_NAME = %s
                """, (safe_col,))
                col_exists = cursor.fetchone()['count'] > 0

                if not col_exists:
                    courses_names[row['Lab Name']] = safe_col
                    alter_query = f"ALTER TABLE student_studied_courses ADD COLUMN `{safe_col}` VARCHAR(50) DEFAULT '0'"
                    cursor.execute(alter_query)

                    cursor.execute("""
                    INSERT INTO helper_student_studied_courses 
                    (name,column_name)
                    VALUES (%s, %s)
                """, (row['Lab Name'],safe_col))

                    db.commit()
                    print(f"✅ Added column '{safe_col}' to student_studied_courses")
                else:
                    print(f"ℹ️ Column '{safe_col}' already exists in student_studied_courses")

            # ✅ Insert into lab_allocations
            # ✅ Check if the exact lab allocation already exists
            cursor.execute("""
                SELECT 1 FROM lab_allocations
                WHERE column_name=%s AND sem_id=%s AND lab_name=%s AND section=%s AND lab_instructor=%s AND strength=%s
            """, (safe_col, semester_id, row['Lab Name'], row['Section'], row['Lab Instructor'], row['Strength']))

            exists = cursor.fetchone()

            if not exists:
                # ✅ Insert if not exists
                
                if row['Lab Instructor'] not in intructor_names:
                    intructor_names.append(row['Lab Instructor'])

                    # genrating the random id
                    id_intructor = ''
                    while(True):
                        id_intructor = str(random.randint(0,20000))+'@nu.edu.pk'
                        if id_intructor not in intructor_id:
                            intructor_id.append(id_intructor)
                            length = 10  # length of the password
                            password = ''.join(random.choices(string.ascii_lowercase, k=length))

                            cursor.execute("""
                                INSERT INTO teacher_login 
                                (name, id, password)
                                VALUES (%s, %s, %s)
                            """, (row['Lab Instructor'],id_intructor,password))

                            break

                    names_and_id_diction[row['Course Instructor']] = id_intructor
                
                    cursor.execute("""
                        INSERT INTO lab_allocations 
                        (column_name, sem_id, lab_name, section, lab_instructor,lab_instructor_id, strength)
                        VALUES (%s, %s, %s, %s, %s, %s,%s)
                    """, (safe_col, semester_id, row['Lab Name'],
                        row['Section'], row['Lab Instructor'],id_intructor, row['Strength']))
                
                else:
                    id_intructor = names_and_id_diction[row["Lab Instructor"]]

                    cursor.execute("""
                        INSERT INTO lab_allocations 
                        (column_name, sem_id, lab_name, section, lab_instructor,lab_instructor_id, strength)
                        VALUES (%s, %s, %s, %s, %s, %s,%s)
                    """, (safe_col, semester_id, row['Lab Name'],
                        row['Section'], row['Lab Instructor'],id_intructor, row['Strength']))




            else:
                print(f"⚠️ Lab allocation already exists for {row['Lab Name']} - {row['Section']} - {row['Lab Instructor']}")


        db.commit()


        return render_template("upload_labs.html", data=df.to_dict(orient="records"), message="File uploaded and data saved successfully!")

    except Exception as e:
        db.rollback()
        print("Error:", e)
        return render_template("upload_labs.html", message=f"Error: {str(e)}")



@app.route("/upload_Courses")
@login_required
def upload_courses():
    return render_template("upload_TA.html")

@app.route("/upload_excel_courses", methods=["POST"])
@login_required
def upload_excel_courses():
    file = request.files.get("file")

    now = datetime.now()
    month = now.month
    year = now.year

    # ✅ Determine semester
    if 1 <= month <= 5:
        semester_id = f"Spring {year}"
    elif 6 <= month <= 7:
        semester_id = f"Summer {year}"
    else:
        semester_id = f"Fall {year}"

    cursor = db.cursor(dictionary=True)

    # ✅ Ensure semester exists
    cursor.execute("SELECT 1 FROM semester_id_data WHERE semester_id = %s", (semester_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO semester_id_data (semester_id) VALUES (%s)", (semester_id,))
        db.commit()
        print(f"Added new semester: {semester_id}")

    # ✅ Fetch existing courses
    cursor.execute("SELECT * FROM helper_student_studied_courses")
    student_courses = cursor.fetchall()
    courses_names = {r['name']: r['column_name'] for r in student_courses}

    if not file:
        return render_template("upload_TA.html", message="No file uploaded!")

    try:
        cursor.execute(f"SELECT * FROM teacher_login")
                     
        row = cursor.fetchall()

        intructor_names = []
        intructor_id = []

        # dictionary will be created having the names and id's
        names_and_id_diction = {}
        
        if row:

            for r in row:
                intructor_names.append(r['name'])
                intructor_id.append(r['id'])

        if row:
            for r in row:
                if r['name'] not in names_and_id_diction:
                    names_and_id_diction[r['name']] = r['id']
            




        # ✅ Read Excel file
        df = pd.read_excel(file, sheet_name='TASheet', skiprows=2)
        df.columns = df.columns.str.strip()  # remove spaces around column names
        

        # Forward-fill the first 3 columns (Course Code, Course Name, Credits)
        df[['Code', 'Course Name', 'CHs']] = df[['Code', 'Course Name', 'CHs']].ffill()

        # Clean the course name: remove parentheses and text inside
        df['Course Name'] = df['Course Name'].str.replace(r'\(.*?\)', '', regex=True).str.strip()

        # Keep only relevant columns
        df = df[['Course Name', 'CHs', 'Section', 'Course Instructor']]

        # Optional: reset index
        df = df.reset_index(drop=True)

        # ✅ Safe column name generator
        def make_safe_column(name):
            print(name,' before')
            name = name.replace(' ', '_').replace('-', '_').replace('&','and').replace('___Repeat','')
            print(name,' after')
            
            return name

        # ✅ Insert each row
        for _, row in df.iterrows():
            print(row)
            safe_col = make_safe_column(row['Course Name'])

            # Add to student_studied_courses if new
            if row['Course Name'] not in courses_names:
                # ✅ Check if column exists in student_studied_courses
                cursor.execute("""
                    SELECT COUNT(*) AS count
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'student_studied_courses'
                    AND COLUMN_NAME = %s
                """, (safe_col,))
                col_exists = cursor.fetchone()['count'] > 0

                if not col_exists:
                    courses_names[row['Course Name']] = safe_col
                    alter_query = f"ALTER TABLE student_studied_courses ADD COLUMN `{safe_col}` VARCHAR(50) DEFAULT '0'"
                    cursor.execute(alter_query)

                    cursor.execute("""
                    INSERT INTO helper_student_studied_courses 
                    (name,column_name)
                    VALUES (%s, %s)
                """, (row['Course Name'],safe_col))

                    db.commit()
                    print(f"✅ Added column '{safe_col}' to student_studied_courses")
                else:
                    print(f"ℹ️ Column '{safe_col}' already exists in student_studied_courses")

            # ✅ Insert into lab_allocations
            # ✅ Check if the exact lab allocation already exists
            cursor.execute("""
                SELECT 1 FROM TA_allocations
                WHERE column_name=%s AND sem_id=%s AND course_name=%s AND section=%s AND course_instructor=%s AND CHs=%s
            """, (safe_col, semester_id, row['Course Name'], row['Section'], row['Course Instructor'], row['CHs']))

            exists = cursor.fetchone()

            if not exists:

                if row['Course Instructor'] not in intructor_names:
                    intructor_names.append(row['Course Instructor'])

                    # genrating the random id
                    id_intructor = ''
                    while(True):
                        id_intructor = str(random.randint(0,20000))+'@nu.edu.pk'
                        if id_intructor not in intructor_id:
                            intructor_id.append(id_intructor)
                            length = 10  # length of the password
                            password = ''.join(random.choices(string.ascii_lowercase, k=length))

                            cursor.execute("""
                                INSERT INTO teacher_login 
                                (name, id, password)
                                VALUES (%s, %s, %s)
                            """, (row['Course Instructor'],id_intructor,password))

                            break
                    
                    names_and_id_diction[row['Course Instructor']] = id_intructor


                    # ✅ Insert if not exists
                    cursor.execute("""
                        INSERT INTO TA_allocations 
                        (column_name, sem_id, course_name, section, course_instructor,course_instructor_id, CHs)
                        VALUES (%s, %s, %s, %s, %s, %s,%s)
                    """, (safe_col, semester_id, row['Course Name'], row['Section'], row['Course Instructor'],id_intructor, row['CHs']))

                else:
                    # ✅ Insert if not exists
                    id_intructor = names_and_id_diction[row['Course Instructor']]
                    
                    print(id_intructor)

                    cursor.execute("""
                        INSERT INTO TA_allocations 
                        (column_name, sem_id, course_name, section, course_instructor,course_instructor_id, CHs)
                        VALUES (%s, %s, %s, %s, %s, %s,%s)
                    """, (safe_col, semester_id, row['Course Name'], row['Section'], row['Course Instructor'],id_intructor, row['CHs']))


            else:
                print(f"⚠️ TA allocation already exists for {row['Course Name']} - {row['Section']} - {row['Course Instructor']}")


        db.commit()


        return render_template("upload_TA.html", data=df.to_dict(orient="records"), message="File uploaded and data saved successfully!")

    except Exception as e:
        db.rollback()
        print("Error:", e)
        return render_template("upload_TA.html", message=f"Error: {str(e)}")


@app.route("/tas/<username>")
@login_required
def tas_page(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)

    # Determine current semester
    now = datetime.now()
    month = now.month
    year = now.year
    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"

    # ---------------- Fetch data for GET ----------------
    # 1. Fetch all courses taught by this instructor
    cursor.execute("""
        SELECT sem_id, course_name, column_name, section,
               course_instructor, course_instructor_id
        FROM TA_allocations
        WHERE course_instructor_id = %s and sem_id=%s
        ORDER BY course_name, section
    """, (username,current_semester))
    allocations = cursor.fetchall()

    print(username,current_semester)
    print(allocations)

    # Organize: course_name -> list of sections
    courses = {}
    for row in allocations:
        cname = row['course_name']
        if cname not in courses:
            courses[cname] = []
        courses[cname].append(row)

    # 2. Fetch TA results for each course/section
    results_data = {}
    for cname, sections in courses.items():
        results_data[cname] = {}
        for sec in sections:
            sem_id = sec['sem_id']
            course_code = sec['column_name']
            section = sec['section']

            cursor.execute("""
                SELECT id, student_id, time_apply, gpa, grade, seniority, rank_, acceptance, submission_files_path
                FROM TA_results_for_Teacher
                WHERE semester=%s AND course_code=%s AND section=%s
                ORDER BY rank_ ASC
            """, (sem_id, course_code, section))

            sec_results = cursor.fetchall()
            results_data[cname][section] = sec_results

    print(results_data)
    return render_template(
        "tas_page.html",
        username=username,
        courses=courses,
        results_data=results_data
    )

import mimetypes

@app.route("/view_submission/<path:sub_path>")
@login_required
def view_submission(sub_path):
    if not os.path.exists(sub_path):
        return "Submission artifacts not found or have been removed.", 404
        
    try:
        # Check if requested as a directory viewer or simple zip/folder structure
        if os.path.isdir(sub_path):
            files = []
            for f in os.listdir(sub_path):
                files.append(f)
            return render_template('view_submission_viewer.html', files=files, base_path=sub_path)
            
        elif os.path.isfile(sub_path):
            directory = os.path.dirname(sub_path)
            filename = os.path.basename(sub_path)
            return send_from_directory(directory, filename)
    except Exception as e:
        return f"Error retrieving artifacts: {str(e)}", 500

@app.route("/update_acceptance/<username>", methods=["POST"])
@login_required
def update_acceptance(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    selected_student = request.form.get("selected_student")
    semester = request.form.get("semester")
    course_code = request.form.get("course_code")
    section = request.form.get("section")

    cursor = db.cursor(dictionary=True)

    # ▶ STEP 1 — Find the previously accepted student (if any)
    cursor.execute("""
        SELECT student_id FROM TA_results_for_Teacher
        WHERE semester=%s AND course_code=%s AND section=%s AND acceptance=1
    """, (semester, course_code, section))
    old_row = cursor.fetchone()

    old_student = old_row['student_id'] if old_row else None

    # ▶ STEP 2 — Reset acceptance for all rows in this section
    cursor.execute("""
        UPDATE TA_results_for_Teacher
        SET acceptance = 0
        WHERE semester=%s AND course_code=%s AND section=%s
    """, (semester, course_code, section))

    # ▶ STEP 3 — If teacher selected a student
    if selected_student:
        # Set acceptance = 1 for new student
        cursor.execute("""
            UPDATE TA_results_for_Teacher
            SET acceptance = 1
            WHERE semester=%s AND course_code=%s AND section=%s AND student_id=%s
        """, (semester, course_code, section, selected_student))

        # Get the submission_files_path for this student
        cursor.execute("""
            SELECT submission_files_path FROM TA_results_for_Teacher
            WHERE semester=%s AND course_code=%s AND section=%s AND student_id=%s
        """, (semester, course_code, section, selected_student))
        file_row = cursor.fetchone()
        file_path = file_row['submission_files_path'] if file_row else None

        # Update TA_allocations
        student_email = f"{selected_student}@nu.edu.pk"
        cursor.execute("""
            UPDATE TA_allocations
            SET s_id=%s, email=%s, allocation_count=1, confirmed=1, submission_files_path=%s
            WHERE sem_id=%s AND column_name=%s AND section=%s AND course_instructor_id=%s
        """, (selected_student, student_email, file_path, semester, course_code, section, username))

        # ▶ STEP 4 — UPDATE student_TA_counter (INCREMENT)
        cursor.execute("""
            SELECT counter FROM student_TA_counter
            WHERE sem_id=%s AND s_id=%s
        """, (semester, selected_student))
        row = cursor.fetchone()

        if row:
            # increment
            new_count = row['counter'] + 1
            cursor.execute("""
                UPDATE student_TA_counter
                SET counter=%s
                WHERE sem_id=%s AND s_id=%s
            """, (new_count, semester, selected_student))
        else:
            # insert first time
            cursor.execute("""
                INSERT INTO student_TA_counter (sem_id, s_id, counter)
                VALUES (%s, %s, 1)
            """, (semester, selected_student))

    # ▶ STEP 5 — HANDLE REMOVAL of old student (if selection changed)
    if old_student and old_student != selected_student:
        cursor.execute("""
            SELECT counter FROM student_TA_counter
            WHERE sem_id=%s AND s_id=%s
        """, (semester, old_student))
        row = cursor.fetchone()

        if row:
            new_count = row['counter'] - 1
            if new_count <= 0:
                # remove entry if zero
                cursor.execute("""
                    DELETE FROM student_TA_counter
                    WHERE sem_id=%s AND s_id=%s
                """, (semester, old_student))
            else:
                cursor.execute("""
                    UPDATE student_TA_counter
                    SET counter=%s
                    WHERE sem_id=%s AND s_id=%s
                """, (new_count, semester, old_student))

        # Also remove TA_allocations entry for old student
        cursor.execute("""
            UPDATE TA_allocations
            SET s_id=NULL, email=NULL, allocation_count=0, confirmed=0
            WHERE sem_id=%s AND column_name=%s AND section=%s AND course_instructor_id=%s
              AND s_id=%s
        """, (semester, course_code, section, username, old_student))

    db.commit()
    return redirect(url_for('tas_page', username=username))


@app.route("/lds/<username>")
@login_required
def lds_page(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    cursor = db.cursor(dictionary=True)

    # Determine current semester
    now = datetime.now()
    month = now.month
    year = now.year
    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"

    # Fetch lab allocations for this teacher and current semester
    cursor.execute("""
        SELECT lab_name, column_name, section,
               s_id_one, email_one, confirmed_one,
               s_id_two, email_two, confirmed_two
        FROM lab_allocations
        WHERE lab_instructor_id=%s AND sem_id=%s
        ORDER BY lab_name, section
    """, (username, current_semester))

    rows = cursor.fetchall()
    # Organize by lab_name → section → students
    labs = {}
    for r in rows:
        lab_name = r['lab_name']
        section = r['section']
        if lab_name not in labs:
            labs[lab_name] = {}
        if section not in labs[lab_name]:
            labs[lab_name][section] = []

        # Add students only if confirmed
        if r['confirmed_one'] == 1:
            labs[lab_name][section].append({
                'rank': 1,
                's_id': r['s_id_one'],
                'email': r['email_one']
            })
        if r['confirmed_two'] == 1:
            labs[lab_name][section].append({
                'rank': 2,
                's_id': r['s_id_two'],
                'email': r['email_two']
            })

    return render_template("lds_page.html", labs=labs, username=username)



@app.route('/view_ta_results/<username>')
@login_required
def view_ta_results(username):
    if username != session.get("username"):
        return redirect(url_for("index"))
    now = datetime.now()
    month = now.month
    year = now.year

    if 1 <= month <= 5:
        current_semester = f"Spring {year}"
    elif 6 <= month <= 7:
        current_semester = f"Summer {year}"
    else:
        current_semester = f"Fall {year}"

   

    query = """
    SELECT course_name, course_instructor, section, sem_id
    FROM TA_allocations
    WHERE s_id = %s AND sem_id = %s
    """
    cursor.execute(query, (username, current_semester))
    results = cursor.fetchall()

    

    return render_template('view_ta_results.html', results=results)


@app.route("/view_ta_results_admin", methods=["GET"])
@login_required
def view_ta_results_admin():
    filter_type = request.args.get("filter", "ALL")  # Default = ALL

    cursor = db.cursor(dictionary=True)

    # Build query based on filter
    if filter_type == "COMPLETED":
        query = """
            SELECT id, sem_id, course_name, section,
                   course_instructor, course_instructor_id,
                   CHs, s_id, email, submission_files_path
            FROM TA_allocations
            WHERE confirmed = 1
            ORDER BY id DESC
        """
    elif filter_type == "NONE":
        query = """
            SELECT id, sem_id, course_name, section,
                   course_instructor, course_instructor_id,
                   CHs, s_id, email, submission_files_path
            FROM TA_allocations
            WHERE confirmed = 0
            ORDER BY id DESC
        """
    else:  # ALL
        query = """
            SELECT id, sem_id, course_name, section,
                   course_instructor, course_instructor_id,
                   CHs, s_id, email, submission_files_path
            FROM TA_allocations
            ORDER BY id DESC
        """

    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()

    return render_template("view_ta_results_admin.html", data=data, filter_type=filter_type)


# ----------------------------chat bot integration ----------------------------------------------------------------------
@app.route("/chatbot")
def open_chatbot():
    # Path to your Streamlit project
    chatbot_dir = r"C:\Users\4G Traders\Desktop\fyp_module1\fyp_module1\rag_chatbot"

    # Virtual environment Python executable
    venv_python = os.path.join(chatbot_dir, "venv", "Scripts", "python.exe")

    # Path to Streamlit script
    streamlit_script = os.path.join(chatbot_dir, "src", "streamlit_app.py")

    # Command to run Streamlit
    cmd = [
        venv_python,
        "-m", "streamlit",
        "run", streamlit_script,
        "--server.port", "8501",
        "--server.headless", "true"
    ]

    # Launch Streamlit in a separate process
    subprocess.Popen(cmd, cwd=chatbot_dir)

    # Redirect user to Streamlit (opens in new browser tab)
    return redirect("http://127.0.0.1:8501", code=302)

# ============================================================
#  EXAM PROCTOR ROUTES (merged from Ep-Y-Fe - Final/app.py)
# ============================================================

@app.route('/exam_portal')
@login_required
def exam_portal():
    return render_template('exam_index.html')

@app.route('/exam_get_courses', methods=['GET'])
def exam_get_courses():
    return jsonify(EXAM_COURSES)

@app.route('/exam_generate', methods=['POST'])
@login_required
def exam_generate():
    data = request.json
    course_name = data.get('course_name')
    role = data.get('role', 'ta')

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
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates exams in JSON format."},
                {"role": "user", "content": prompt}
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


@app.route('/exam_grade_short', methods=['POST'])
@login_required
def exam_grade_short():
    data = request.json
    course = data.get('course', 'General')
    qa_pairs = data.get('qa_pairs', [])

    if not qa_pairs:
        return jsonify({"error": "No questions/answers provided"}), 400

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
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a strict but fair academic examiner. Always respond with valid JSON only."},
                {"role": "user", "content": grading_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = chat_completion.choices[0].message.content
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            grades = parsed
        elif isinstance(parsed, dict):
            grades = parsed.get('grades') or parsed.get('results') or parsed.get('answers') or list(parsed.values())[0]
        else:
            grades = []
        return jsonify({"grades": grades})
    except Exception as e:
        print(f"Error grading answers: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/exam_run_code', methods=['POST'])
@login_required
def exam_run_code():
    data = request.json
    language = data.get('language', 'python').lower()
    code = data.get('code', '')

    if language not in LANGUAGE_IDS:
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    lang_id = LANGUAGE_IDS[language]

    try:
        payload = {"source_code": code, "language_id": lang_id, "stdin": ""}
        resp = http_requests.post(f"{JUDGE0_URL}/submissions?wait=true", json=payload, timeout=20)

        if resp.status_code in [200, 201]:
            result = resp.json()
            stdout = result.get('stdout') or ''
            stderr = result.get('stderr') or result.get('compile_output') or ''
            status = result.get('status', {}).get('description', 'Unknown')
            if "error" in status.lower() or "blocked" in status.lower():
                return _exam_run_with_llm(language, code)
            return jsonify({"stdout": stdout, "stderr": stderr, "status": status, "is_llm_simulated": False})
        
        print(f"Judge0 error (HTTP {resp.status_code}): {resp.text}")
        return _exam_run_with_llm(language, code)
    except Exception as e:
        print(f"Code runner exception: {str(e)}")
        return _exam_run_with_llm(language, code)


def _exam_run_with_llm(language, code):
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
        completion = groq_client.chat.completions.create(
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
        if language == 'python':
            return _exam_run_python_locally(code)
        return jsonify({"stdout": "", "stderr": f"Offline execution failed. Error: {str(e)}", "status": "Service Unavailable"})


def _exam_run_python_locally(code):
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            fname = f.name
        try:
            result = subprocess.run(['python', fname], capture_output=True, text=True, timeout=10)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)
        return jsonify({"stdout": result.stdout, "stderr": result.stderr, "status": "Accepted" if result.returncode == 0 else "Runtime Error"})
    except subprocess.TimeoutExpired:
        return jsonify({"stdout": "", "stderr": "Execution timed out (10s).", "status": "Time Limit Exceeded"})
    except Exception as e:
        return jsonify({"stdout": "", "stderr": str(e), "status": "Error"})


def _exam_grade_coding(course, language, question, code, expected_output):
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
        completion = groq_client.chat.completions.create(
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


@app.route('/exam_transcribe', methods=['POST'])
@login_required
def exam_transcribe():
    import uuid
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    filename = f"temp_audio_{uuid.uuid4().hex[:8]}.wav"
    audio_file.save(filename)

    try:
        with open(filename, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                response_format="json",
                language="en",
                temperature=0.0
            )
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({"text": transcription.text})
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({"error": str(e)}), 500


@app.route('/exam_submit', methods=['POST'])
@login_required
def exam_submit():
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
        qa_pairs = [{"question": a.get('question'), "answer": a.get('answer')} for a in sa_data]

        grades = []
        try:
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

            chat_completion = groq_client.chat.completions.create(
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
    coding_grade = {}
    if coding_answer and role == 'ld':
        results_text += "--- CODING QUESTION ---\n"
        coding_question_text = request.form.get('coding_question', 'N/A')
        try:
            coding_grade = _exam_grade_coding(
                course_name, coding_language, coding_question_text, 
                coding_answer, "Check logic against problem statement"
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
    for f_name in os.listdir(student_folder):
        if f_name.startswith('audio_q') and f_name.endswith('.wav'):
            audio_paths.append(os.path.join(student_folder, f_name))

    video_path = os.path.join(student_folder, "full_session.mp4") if video_saved else None

    avg_tone, avg_conf = exam_analyzer.analyze_audio(audio_paths)
    avg_video = exam_analyzer.analyze_video(video_path) if video_path else 50.0

    c_score = 0
    if coding_answer and role == 'ld':
        try:
            c_score = int(coding_grade.get('score', 0))
        except:
            c_score = 0

    final_report = exam_analyzer.calculate_final_score(
        mcq_score=mcq_score, mcq_denom=5,
        short_score=short_total_score, short_denom=25,
        coding_score=c_score, coding_denom=20 if (coding_answer and role == 'ld') else 1,
        avg_conf=avg_conf, avg_tone=avg_tone, avg_video=avg_video
    )

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

    utils.save_text_file(student_folder, "results.txt", results_text)
    utils.save_text_file(student_folder, "summary.json", json.dumps(final_report, indent=2))

    # --- DB SYNCHRONIZATION ---
    try:
        exam_cursor = db.cursor(dictionary=True)
        # Get the latest launch
        launch_table = "launch_selection_TA" if role == 'ta' else "launch_selection"
        exam_cursor.execute(f"SELECT id FROM {launch_table} ORDER BY id DESC LIMIT 1")
        launch_row = exam_cursor.fetchone()
        
        if launch_row:
            launch_id = launch_row['id']
            app_table = "student_applications_TA" if role == 'ta' else "student_applications"
            
            # The course_name from form could be "Programming Fundamentals Lab"
            # But the DB stores it as "Programming_Fundamentals_Lab", so we check both
            course_code_underscored = course_name.replace(' ', '_')
            
            # Update the specific application for this launch
            update_query = f"""
                UPDATE {app_table} 
                SET interview_taken = 1, interview_marks = %s, submission_files_path = %s
                WHERE username = %s AND (course_code = %s OR course_code = %s OR course_code LIKE %s) AND launch_id = %s
            """
            exam_cursor.execute(update_query, (
                final_report['final_score'], 
                os.path.abspath(student_folder),
                student_id, 
                course_name, 
                course_code_underscored,
                f"%{course_name}%",
                launch_id
            ))
            db.commit()
            print(f"Successfully updated DB for {student_id} in {course_name} (Launch ID: {launch_id})")
        else:
            print("DB Sync Error: No active launch round found.")
        exam_cursor.close()
    except Exception as e:
        db.rollback()
        print(f"DB Sync Error: {e}")

    return jsonify({
        "message": "Exam submitted and analyzed successfully",
        "folder": student_folder,
        "final_score": final_report['final_score']
    })

# ============================================================
#  END OF EXAM PROCTOR ROUTES
# ============================================================


check_and_schedule_latest_launch_for_ld()

check_and_schedule_latest_launch_TA()

if __name__ == "__main__":
    app.run(debug=True)

    #update the cursor for each 
