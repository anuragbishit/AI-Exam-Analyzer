from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)

import sqlite3
import random
import json
import hashlib
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

from google import genai
from question_analytics import ensure_question_attempts_table, save_question_attempts
from mastery_engine import calculate_topic_mastery
from knowledge_gap_engine import calculate_knowledge_gaps, build_knowledge_gap_prompt
from study_plan_engine import build_draft_study_plan, save_study_plan, get_active_study_plan, toggle_plan_item

load_dotenv()


# ───────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────

app = Flask(__name__)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

app.secret_key = "ai_exam_secret_key_2024"

# SECURITY SETTINGS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False


# ─────────────────────────────────────────────
# GEMINI AI CONFIG
# ─────────────────────────────────────────────

# PASTE YOUR REAL API KEY IN .env FILE OR BELOW
API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)


# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

DATABASE = "database.db"


def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


def create_tables():

    with get_db() as conn:

        cursor = conn.cursor()

        # STUDENTS TABLE
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                admin_id INTEGER
            )
            '''
        )
        
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN admin_id INTEGER")
        except:
            pass

        # EXAM HISTORY TABLE
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS exam_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                weak_topics TEXT DEFAULT '',
                exam_date TEXT NOT NULL
            )
            '''
        )
        
        try:
            cursor.execute("ALTER TABLE exam_history ADD COLUMN is_global INTEGER DEFAULT 0")
        except:
            pass

        try:
            cursor.execute("ALTER TABLE exam_history ADD COLUMN subject_area TEXT DEFAULT 'General'")
        except:
            pass

        # ADMINS TABLE
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            '''
        )

        # STUDY PLANS
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS study_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                duration_days INTEGER NOT NULL DEFAULT 7,
                status TEXT NOT NULL DEFAULT 'draft',
                generation_method TEXT NOT NULL DEFAULT 'rule_based',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS study_plan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'Day Focus',
                topic TEXT NOT NULL,
                subtopic TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                recommended_minutes INTEGER NOT NULL DEFAULT 30,
                objective TEXT NOT NULL,
                practice_questions INTEGER NOT NULL DEFAULT 10,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            '''
        )

        # Backward-compatible columns for existing study-plan databases.
        plan_columns = {row[1] for row in cursor.execute('PRAGMA table_info(study_plan_items)').fetchall()}
        if 'title' not in plan_columns:
            cursor.execute("ALTER TABLE study_plan_items ADD COLUMN title TEXT DEFAULT 'Day Focus'")
        if 'completed_at' not in plan_columns:
            cursor.execute("ALTER TABLE study_plan_items ADD COLUMN completed_at TEXT")

        plan_table_columns = {row[1] for row in cursor.execute('PRAGMA table_info(study_plans)').fetchall()}
        if 'generation_method' not in plan_table_columns:
            cursor.execute("ALTER TABLE study_plans ADD COLUMN generation_method TEXT DEFAULT 'rule_based'")

        # INSERT DEFAULT ADMIN IF NOT EXISTS
        cursor.execute('SELECT COUNT(*) as c FROM admins')
        if cursor.fetchone()['c'] == 0:
            cursor.execute(
                '''
                INSERT INTO admins (email, password)
                VALUES (?, ?)
                ''',
                ('admin@exam.com', hash_password('admin123'))
            )

        conn.commit()

    ensure_question_attempts_table(get_db)


# ─────────────────────────────────────────────
# PASSWORD HASHING
# ─────────────────────────────────────────────

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()

create_tables()


# ─────────────────────────────────────────────
# QUESTION BANK
# ─────────────────────────────────────────────

QUESTIONS = [

    {
        'question': 'What is the brain of a computer?',
        'options': [
            'RAM',
            'CPU',
            'Keyboard',
            'Mouse'
        ],
        'answer': 'CPU',
        'topic': 'Computer Fundamentals'
    },

    {
        'question': 'Which programming language is used in Flask?',
        'options': [
            'Java',
            'Python',
            'C++',
            'PHP'
        ],
        'answer': 'Python',
        'topic': 'Web Frameworks'
    },

    {
        'question': 'Which database does this project use?',
        'options': [
            'Oracle',
            'MongoDB',
            'SQLite',
            'Firebase'
        ],
        'answer': 'SQLite',
        'topic': 'Database Systems'
    },

    {
        'question': 'What does HTML stand for?',
        'options': [
            'Hyper Text Markup Language',
            'High Tech Modern Language',
            'Hyper Transfer Markup Logic',
            'Home Tool Markup Language'
        ],
        'answer': 'Hyper Text Markup Language',
        'topic': 'Web Development'
    },

    {
        'question': 'Which HTTP method is used to submit a form?',
        'options': [
            'GET',
            'POST',
            'PUT',
            'DELETE'
        ],
        'answer': 'POST',
        'topic': 'Web Development'
    },

    {
        'question': 'What is the time complexity of Binary Search?',
        'options': [
            'O(n)',
            'O(n²)',
            'O(log n)',
            'O(1)'
        ],
        'answer': 'O(log n)',
        'topic': 'Data Structures'
    },

    {
        'question': 'Which data structure follows LIFO?',
        'options': [
            'Queue',
            'Stack',
            'Array',
            'Tree'
        ],
        'answer': 'Stack',
        'topic': 'Data Structures'
    },

    {
        'question': 'What does CSS stand for?',
        'options': [
            'Computer Style Sheets',
            'Cascading Style Sheets',
            'Creative Style System',
            'Colorful Style Syntax'
        ],
        'answer': 'Cascading Style Sheets',
        'topic': 'Web Development'
    },

    {
        'question': 'Which is NOT an Operating System?',
        'options': [
            'Linux',
            'Windows',
            'Oracle',
            'macOS'
        ],
        'answer': 'Oracle',
        'topic': 'Operating Systems'
    },

    {
        'question': 'What does SQL stand for?',
        'options': [
            'Structured Query Language',
            'Simple Question Language',
            'Sequential Query Logic',
            'Standard Question List'
        ],
        'answer': 'Structured Query Language',
        'topic': 'Database Systems'
    }
]


# ─────────────────────────────────────────────
# TOPIC RECOMMENDATIONS
# ─────────────────────────────────────────────

TOPIC_RECOMMENDATIONS = {

    'Computer Fundamentals':
        'Study CPU, RAM and memory hierarchy.',

    'Web Frameworks':
        'Practice Flask routing and templates.',

    'Database Systems':
        'Revise SQL and normalization.',

    'Web Development':
        'Practice HTML, CSS and JavaScript.',

    'Data Structures':
        'Practice stack, queue and search algorithms.',

    'Operating Systems':
        'Revise scheduling and memory management.'
}


def get_recommendation(topic):

    if topic in TOPIC_RECOMMENDATIONS:
        return TOPIC_RECOMMENDATIONS[topic]

    return f'Review fundamental concepts of {topic} and practice related problems.'


# ─────────────────────────────────────────────
# AI RESPONSE CLEANER
# ─────────────────────────────────────────────

def clean_ai_response(text):

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    if text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ─────────────────────────────────────────────
# GEMINI GENERATION HELPER
# ─────────────────────────────────────────────

def generate_ai_content(prompt):
    """Generate AI content with fast fallback across currently supported Gemini Flash models."""
    import time

    # Prefer the high-capacity, cost-efficient Flash-Lite model first.
    # Fall back to newer Flash models when a model is temporarily busy.
    models = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
    ]

    last_error = None

    for attempt in range(len(models)):
        model = models[attempt]

        try:
            print(f"AI generation attempt {attempt + 1}/{len(models)} using {model}")

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if response and getattr(response, "text", None):
                print(f"AI generation succeeded using {model}")
                return response.text

            last_error = Exception(f"Empty AI response from {model}")

        except Exception as e:
            last_error = e
            message = str(e).lower()

            transient = (
                "503" in message
                or "429" in message
                or "unavailable" in message
                or "high demand" in message
                or "quota" in message
            )

            print(f"AI generation failed on {model}: {e}")

            if not transient:
                raise

            # Give the next model a small delay, but do not keep the browser
            # waiting through a long retry loop.
            if attempt < len(models) - 1:
                time.sleep(2)

    raise last_error or Exception("Gemini AI generation failed")

# ─────────────────────────────────────────────
# AI QUESTION VALIDATOR
# ─────────────────────────────────────────────

def validate_questions(questions, topic):

    cleaned_questions = []

    for q in questions:

        if not isinstance(q, dict):
            continue

        if 'question' not in q:
            continue

        if 'options' not in q:
            continue

        if 'answer' not in q:
            continue

        question_text = str(q['question']).strip()

        options = q['options']

        answer = str(q['answer']).strip()

        if not question_text:
            continue

        if not isinstance(options, list):
            continue

        if len(options) < 4:
            continue

        options = [str(opt).strip() for opt in options[:4]]

        options = [opt for opt in options if opt]

        if len(options) < 4:
            continue

        matched_answer = None

        for opt in options:

            if answer.lower() == opt.lower():
                matched_answer = opt
                break

        if not matched_answer:
            continue

        recommendation = str(q.get('recommendation', '')).strip()
        subtopic = str(q.get('subtopic', '')).strip() or topic

        cleaned_questions.append({
            'question': question_text,
            'options': options,
            'answer': matched_answer,
            'topic': topic,
            'subtopic': subtopic,
            'recommendation': recommendation
        })

    return cleaned_questions


# ─────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────

@app.route('/')
def home():

    if 'student_id' in session:
        return redirect('/dashboard')

    return render_template('index.html')


# ─────────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if 'student_id' in session:
        return redirect('/dashboard')

    error = None

    if request.method == 'POST':

        name = request.form.get('name', '').strip()

        email = request.form.get('email', '').strip().lower()

        password = request.form.get('password', '')

        if not name or not email or not password:

            error = 'All fields are required.'

        elif len(password) < 6:

            error = 'Password must be at least 6 characters.'

        else:

            try:

                with sqlite3.connect(DATABASE) as conn:

                    conn.execute(
                        '''
                        INSERT INTO students
                        (name, email, password, admin_id)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (
                            name,
                            email,
                            hash_password(password),
                            1 # Default to admin 1
                        )
                    )

                    conn.commit()

                return redirect('/student_login?success=1')

            except sqlite3.IntegrityError:

                error = 'Email already exists.'

    return render_template(
        'signup.html',
        error=error
    )


# ─────────────────────────────────────────────
# LOGIN SELECTION
# ─────────────────────────────────────────────

@app.route('/login')
def login_selection():
    if 'student_id' in session:
        return redirect('/dashboard')
    return render_template('login_selection.html')


# ─────────────────────────────────────────────
# STUDENT LOGIN
# ─────────────────────────────────────────────

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():

    if 'student_id' in session:
        if session.get('mode') == 'global':
            return redirect('/global_leaderboard')
        return redirect('/dashboard')

    error = None

    success = request.args.get('success')
    mode = request.args.get('mode', 'practice')

    if request.method == 'POST':

        email = request.form.get(
            'email',
            ''
        ).strip().lower()

        password = request.form.get(
            'password',
            ''
        )

        conn = get_db()

        student = conn.execute(
            '''
            SELECT * FROM students
            WHERE email=? AND password=?
            ''',
            (
                email,
                hash_password(password)
            )
        ).fetchone()

        conn.close()

        if student:

            session['student_id'] = student['id']

            session['student_name'] = student['name']
            
            session['mode'] = mode

            if mode == 'global':
                return redirect('/global_leaderboard')
            return redirect('/dashboard')

        else:

            error = 'Invalid email or password.'

    return render_template(
        'login.html',
        error=error,
        success=success,
        mode=mode
    )


# ─────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# ─────────────────────────────────────────────
# FORGOT PASSWORD
# ─────────────────────────────────────────────

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():

    if 'student_id' in session:
        return redirect('/dashboard')

    error = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        conn = get_db()
        student = conn.execute(
            'SELECT * FROM students WHERE email=?', 
            (email,)
        ).fetchone()
        conn.close()

        if student:
            otp = str(random.randint(100000, 999999))
            session['reset_email'] = email
            session['reset_otp'] = otp
            session['otp_verified'] = False
            
            # Send OTP via email
            sender_email = os.environ.get("SMTP_EMAIL")
            sender_password = os.environ.get("SMTP_PASSWORD")
            if sender_email and sender_password:
                try:
                    msg = MIMEText(f"Hello {student['name']},\n\nYour OTP for password reset is: {otp}\n\nIf you did not request this, please ignore this email.")
                    msg['Subject'] = "Your Password Reset OTP"
                    msg['From'] = sender_email
                    msg['To'] = email
                    
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(sender_email, sender_password)
                        server.send_message(msg)
                except Exception as e:
                    print(f"Failed to send email: {e}")
                    # You might want to flash an error or handle it gracefully
            
            return redirect('/verify_otp')
        else:
            error = 'No account found with that email address.'

    return render_template('forgot_password.html', error=error)


# ─────────────────────────────────────────────
# VERIFY OTP
# ─────────────────────────────────────────────

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():

    if 'student_id' in session:
        return redirect('/dashboard')

    if 'reset_email' not in session or 'reset_otp' not in session:
        return redirect('/forgot_password')

    error = None
    
    # For demonstration purposes, we will pass the OTP to the template so it can be displayed
    demo_otp = session.get('reset_otp')

    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()
        
        if user_otp == session['reset_otp']:
            session['otp_verified'] = True
            return redirect('/reset_password')
        else:
            error = 'Invalid OTP. Please try again.'

    return render_template('verify_otp.html', error=error, demo_otp=demo_otp)


# ─────────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────────

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():

    if 'student_id' in session:
        return redirect('/dashboard')

    if 'reset_email' not in session or not session.get('otp_verified'):
        return redirect('/forgot_password')

    error = None

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or not confirm_password:
            error = 'Both fields are required.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'
        else:
            email = session['reset_email']
            conn = get_db()
            conn.execute(
                'UPDATE students SET password=? WHERE email=?',
                (hash_password(password), email)
            )
            conn.commit()
            conn.close()
            
            session.pop('reset_email', None)
            session.pop('reset_otp', None)
            session.pop('otp_verified', None)
            return redirect('/login?success=2')

    return render_template('reset_password.html', error=error)



# ─────────────────────────────────────────────
# PERSONALIZED STUDY PLAN
# ─────────────────────────────────────────────

@app.route('/study_plan')
def study_plan():
    if 'student_id' not in session:
        return redirect('/login')

    conn = get_db()
    plan = get_active_study_plan(conn, session['student_id'])
    conn.close()

    return render_template(
        'study_plan.html',
        plan=plan
    )


@app.route('/study_plan/generate', methods=['POST'])
def generate_study_plan():
    if 'student_id' not in session:
        return redirect('/login')

    sid = session['student_id']
    conn = get_db()

    topic_mastery = calculate_topic_mastery(conn, sid)
    knowledge_gaps = calculate_knowledge_gaps(conn, sid)

    plan = build_draft_study_plan(
        topic_mastery,
        knowledge_gaps,
        days=7
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Archive an existing active/draft plan before creating a new one.
    conn.execute(
        """
        UPDATE study_plans
        SET status='archived', updated_at=?
        WHERE student_id=? AND status IN ('active', 'draft')
        """,
        (now, sid)
    )

    plan['status'] = 'active'
    plan_id = save_study_plan(conn, sid, plan)
    conn.close()

    return redirect(f'/study_plan?generated=1&id={plan_id}')


@app.route('/study_plan/item/<int:item_id>/toggle', methods=['POST'])
def toggle_study_plan_item(item_id):
    if 'student_id' not in session:
        return redirect('/login')

    conn = get_db()
    success = toggle_plan_item(
        conn,
        session['student_id'],
        item_id
    )
    conn.close()

    return redirect('/study_plan?updated=1' if success else '/study_plan')

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():

    if 'student_id' not in session:
        return redirect('/login')

    sid = session['student_id']

    name = session['student_name']

    conn = get_db()

    tests_taken = conn.execute(
        '''
        SELECT COUNT(*) as c
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()['c']

    avg_row = conn.execute(
        '''
        SELECT SUM(score) as total_score, SUM(total_questions) as total_qs
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    if avg_row and avg_row['total_qs'] and avg_row['total_qs'] > 0:
        average_score = round(avg_row['total_score'] * 100.0 / avg_row['total_qs'])
    else:
        average_score = 0

    best_row = conn.execute(
        '''
        SELECT MAX(score * 100.0 / total_questions) as b
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    best_score = round(best_row['b']) if best_row['b'] else 0

    history = conn.execute(
        '''
        SELECT
            score,
            total_questions,
            weak_topics,
            exam_date
        FROM exam_history
        WHERE student_id=?
        ORDER BY id DESC
        LIMIT 10
        ''',
        (sid,)
    ).fetchall()

    topic_counts = {}

    rows = conn.execute(
        '''
        SELECT weak_topics
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchall()

    for row in rows:

        if row['weak_topics']:

            for t in row['weak_topics'].split('||'):

                t = t.strip()

                if t:

                    topic_counts[t] = (
                        topic_counts.get(t, 0) + 1
                    )

    total_weak = sum(topic_counts.values())

    question_summary = conn.execute(
        '''
        SELECT COUNT(*) AS total_attempts,
               COALESCE(SUM(is_correct), 0) AS correct_attempts,
               COALESCE(AVG(response_time_seconds), 0) AS avg_response_time,
               COALESCE(MAX(response_time_seconds), 0) AS max_response_time
        FROM question_attempts
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    topic_mastery = calculate_topic_mastery(conn, sid)
    knowledge_gaps = calculate_knowledge_gaps(conn, sid)
    active_study_plan = get_active_study_plan(conn, sid)

    chart_labels = []

    chart_scores = []

    chart_rows = conn.execute(
        '''
        SELECT
            score,
            total_questions,
            exam_date
        FROM exam_history
        WHERE student_id=?
        ORDER BY id DESC
        LIMIT 10
        ''',
        (sid,)
    ).fetchall()

    # Reverse to plot chronological order (left to right)
    chart_rows = list(reversed(chart_rows))

    for row in chart_rows:

        pct = round(
            row['score'] * 100.0 / row['total_questions']
        ) if row['total_questions'] else 0

        # Format as MM-DD HH:MM
        chart_labels.append(
            row['exam_date'][5:16]
        )

        chart_scores.append(pct)

    conn.close()

    return render_template(
        'dashboard.html',
        name=name,
        tests_taken=tests_taken,
        average_score=average_score,
        best_score=best_score,
        total_weak=total_weak,
        history=history,
        topic_counts=topic_counts,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        topic_recommendations=TOPIC_RECOMMENDATIONS,
        question_summary=question_summary,
        topic_mastery=topic_mastery,
        knowledge_gaps=knowledge_gaps,
        active_study_plan=active_study_plan
    )


# ─────────────────────────────────────────────
# STATISTICS
# ─────────────────────────────────────────────

@app.route('/statistics')
def statistics():

    if 'student_id' not in session:
        return redirect('/login')

    sid = session['student_id']

    name = session['student_name']

    conn = get_db()

    tests_taken = conn.execute(
        '''
        SELECT COUNT(*) as c
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()['c']

    avg_row = conn.execute(
        '''
        SELECT SUM(score) as total_score, SUM(total_questions) as total_qs
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    total_score = avg_row['total_score'] if avg_row and avg_row['total_score'] else 0
    total_qs = avg_row['total_qs'] if avg_row and avg_row['total_qs'] else 0

    if total_qs > 0:
        average_score = round(total_score * 100.0 / total_qs)
    else:
        average_score = 0

    best_row = conn.execute(
        '''
        SELECT MAX(score * 100.0 / total_questions) as b
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    best_score = round(best_row['b']) if best_row['b'] else 0

    topic_counts = {}

    rows = conn.execute(
        '''
        SELECT weak_topics
        FROM exam_history
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchall()

    for row in rows:

        if row['weak_topics']:

            for t in row['weak_topics'].split('||'):

                t = t.strip()

                if t:

                    topic_counts[t] = (
                        topic_counts.get(t, 0) + 1
                    )

    total_weak = sum(topic_counts.values())

    question_summary = conn.execute(
        '''
        SELECT COUNT(*) AS total_attempts,
               COALESCE(SUM(is_correct), 0) AS correct_attempts,
               COALESCE(AVG(response_time_seconds), 0) AS avg_response_time,
               COALESCE(MAX(response_time_seconds), 0) AS max_response_time
        FROM question_attempts
        WHERE student_id=?
        ''',
        (sid,)
    ).fetchone()

    question_topic_stats = conn.execute(
        '''
        SELECT topic,
               subtopic,
               COUNT(*) AS attempts,
               COALESCE(SUM(is_correct), 0) AS correct,
               COALESCE(AVG(response_time_seconds), 0) AS avg_response_time
        FROM question_attempts
        WHERE student_id=?
        GROUP BY topic, subtopic
        ORDER BY attempts DESC
        ''',
        (sid,)
    ).fetchall()

    topic_mastery = calculate_topic_mastery(conn, sid)
    knowledge_gaps = calculate_knowledge_gaps(conn, sid)

    conn.close()

    return render_template(
        'statistics.html',
        name=name,
        tests_taken=tests_taken,
        average_score=average_score,
        total_score=total_score,
        total_qs=total_qs,
        best_score=best_score,
        total_weak=total_weak,
        topic_counts=topic_counts,
        question_summary=question_summary,
        question_topic_stats=question_topic_stats,
        topic_mastery=topic_mastery,
        knowledge_gaps=knowledge_gaps
    )


# ─────────────────────────────────────────────
# EXAM SETUP
# ─────────────────────────────────────────────

@app.route('/exam')
def exam_setup():

    if 'student_id' not in session:
        return redirect('/login')

    return render_template('exam_setup.html')





# ─────────────────────────────────────────────
# AI GENERATED EXAM
# ─────────────────────────────────────────────

@app.route('/ai_exam', methods=['POST'])
def ai_exam():

    if 'student_id' not in session:
        return redirect('/login')

    subject = request.form.get('subject', '').strip()
    topic = request.form.get('topic', '').strip()
    difficulty = request.form.get('difficulty', 'medium').strip()
    question_type = request.form.get('question_type', 'both').strip()

    if topic == '':
        return render_template(
            'exam_setup.html',
            error='Please enter a topic'
        )

    try:
        count = int(request.form.get('count', 5))
    except:
        count = 5

    count = max(1, min(count, 20))

    if question_type == 'theoretical':
        type_prompt = "The questions should be purely theoretical."
    elif question_type == 'numerical':
        type_prompt = "The questions should be purely numerical or calculation-based."
    else:
        type_prompt = "The questions should be a mix of theoretical and numerical."

    prompt = f"""
Generate exactly {count} {difficulty} level multiple choice questions about the topic "{topic}" within the broader subject of "{subject}".
{type_prompt}

Rules:
1. Each question must have exactly 4 options
2. Only one option should be correct
3. Return ONLY a valid JSON array.
4. Do not add explanation
5. VERY IMPORTANT: Escape all double quotes inside strings (use \\").

Format:
[
  {{
    "question": "Question here",
    "options": ["A", "B", "C", "D"],
    "answer": "Correct Option",
    "topic": "Topic Name",
    "subtopic": "Specific concept or sub-topic tested by this question",
    "recommendation": "Provide a very specific concept, sub-topic, or formula to study related to this exact question."
  }}
]
"""

    try:

        text = generate_ai_content(prompt)

        text = clean_ai_response(text)

        start = text.find('[')

        end = text.rfind(']') + 1

        if start == -1 or end == 0:
            raise Exception("JSON array not found")

        json_text = text[start:end]

        questions = json.loads(json_text)

        cleaned_questions = validate_questions(
            questions,
            topic
        )

        for q in cleaned_questions:
            q['difficulty'] = difficulty
            q['subtopic'] = str(q.get('subtopic', '')).strip() or topic

        if len(cleaned_questions) == 0:
            raise Exception("No valid questions generated")

        session['questions'] = cleaned_questions
        session['exam_topic'] = topic
        session['exam_mode'] = 'ai_generated'

        try:
            duration = int(request.form.get('duration', 10))
        except:
            duration = 10

        return render_template(
            'exam.html',
            questions=cleaned_questions,
            total=len(cleaned_questions),
            duration=duration
        )

    except Exception as e:

        print("AI ERROR:", e)

        return render_template(
            'exam_setup.html',
            error=f'Failed to generate AI questions: {str(e)}'
        )



# ─────────────────────────────────────────────
# AI PRACTICE FROM MISTAKES
# ─────────────────────────────────────────────

def generate_practice_questions(topics, count=10):
    """Generate a targeted practice exam from the student's weak topics."""
    if not topics:
        raise ValueError("No weak topics available for practice.")

    safe_count = max(1, min(int(count), 20))
    topic_text = ", ".join(topics[:8])

    prompt = f'''Create exactly {safe_count} multiple-choice practice questions focused on these weak topics:
{topic_text}

The questions are for a student who previously answered questions incorrectly in these areas.
Requirements:
1. Cover the listed weak topics as evenly as possible.
2. Mix conceptual and application-oriented questions.
3. Difficulty should be adaptive: mostly easy/medium, with a small number of challenging questions.
4. Every question must have exactly 4 unique options.
5. Exactly one option must be correct.
6. Do not repeat the same question or use trivial wording.
7. The "topic" field must contain the specific weak topic being tested.
8. The "recommendation" field must name the exact concept to review if the student gets the question wrong.
9. Return ONLY a valid JSON array.

Format:
[
  {{
    "question": "Question here",
    "options": ["A", "B", "C", "D"],
    "answer": "Correct Option",
    "topic": "Specific Topic",
    "subtopic": "Specific concept tested",
    "recommendation": "Specific concept or sub-topic to review"
  }}
]'''

    text = generate_ai_content(prompt)
    start = text.find('[')
    end = text.rfind(']') + 1
    if start == -1 or end <= 0:
        raise Exception("JSON array not found")

    questions = json.loads(text[start:end])
    cleaned = validate_questions(questions, topics[0])

    # The shared validator intentionally normalizes topics for ordinary exams.
    # For mistake practice, restore the specific weak-topic label by cycling
    # through the requested topics so analytics remain meaningful.
    if len(cleaned) > 1 and len(topics) > 1:
        for index, q in enumerate(cleaned):
            q['topic'] = topics[index % len(topics)]

    if len(cleaned) < max(1, min(3, safe_count)):
        raise Exception("AI returned too few valid practice questions")

    normalized_topics = {t.strip().lower(): t.strip() for t in topics if t.strip()}
    for q in cleaned:
        ai_topic = str(q.get("topic", "")).strip()
        q["topic"] = normalized_topics.get(ai_topic.lower(), ai_topic or topics[0])
        q["subtopic"] = str(q.get("subtopic", "")).strip() or q["topic"]
        q["difficulty"] = "adaptive"

    return cleaned


@app.route('/practice_from_mistakes', methods=['POST'])
def practice_from_mistakes():
    if 'student_id' not in session:
        return redirect('/login')

    conn = get_db()
    rows = conn.execute(
        '''SELECT weak_topics FROM exam_history
           WHERE student_id=? AND weak_topics != ''
           ORDER BY id DESC LIMIT 5''',
        (session['student_id'],)
    ).fetchall()
    conn.close()

    topics = []
    for row in rows:
        for topic in (row['weak_topics'] or '').split('||'):
            topic = topic.strip()
            if topic and topic not in topics:
                topics.append(topic)

    if not topics:
        return render_template(
            'exam_setup.html',
            error='Take an exam and make some mistakes first. Your weak topics will appear here.'
        )

    try:
        questions = generate_practice_questions(topics, 10)
        session['questions'] = questions
        session['exam_topic'] = "AI Practice: " + ", ".join(topics[:4])
        session['exam_mode'] = 'practice_from_mistakes'

        return render_template(
            'exam.html',
            questions=questions,
            total=len(questions),
            duration=10,
            practice_mode=True,
            practice_topics=topics[:8]
        )
    except Exception as e:
        print("PRACTICE AI ERROR:", e)
        return render_template(
            'exam_setup.html',
            error=f'Failed to generate practice questions: {str(e)}'
        )

# ─────────────────────────────────────────────
# SUBMIT EXAM
# ─────────────────────────────────────────────

@app.route('/submit_exam', methods=['POST'])
def submit_exam():

    if 'student_id' not in session:
        return redirect('/login')

    questions = session.get('questions', QUESTIONS)

    score = 0

    weak_topics = []

    wrong_details = []

    for i, q in enumerate(questions):

        selected = request.form.get(f'q{i}')

        if selected == q['answer']:

            score += 1

        else:

            weak_topics.append(q['topic'])

            wrong_details.append({

                'question': q['question'],

                'your_answer': selected or 'Not answered',

                'correct_answer': q['answer'],

                'topic': q['topic'],

                'subtopic': q.get('subtopic') or q['topic'],

                'recommendation': q.get('recommendation') or get_recommendation(q['topic'])

            })

    unique_weak = list(dict.fromkeys(weak_topics))

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            '''
            INSERT INTO exam_history
            (student_id, student_name, score, total_questions, weak_topics, exam_date, is_global, subject_area)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                session['student_id'],
                session['student_name'],
                score,
                len(questions),
                '||'.join(unique_weak),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                1 if session.get('mode') == 'global' else 0,
                session.get('exam_topic', 'General')
            )
        )

        conn.commit()

    percentage = round(score * 100 / len(questions))

    if percentage >= 80:
        grade = 'Excellent'

    elif percentage >= 60:
        grade = 'Good'

    elif percentage >= 40:
        grade = 'Average'

    else:
        grade = 'Needs Improvement'

    return render_template(
        'result.html',
        score=score,
        total=len(questions),
        percentage=percentage,
        grade=grade,
        wrong_details=wrong_details,
        unique_weak=unique_weak
    )


# ─────────────────────────────────────────────
# SAVE EXAM AJAX
# ─────────────────────────────────────────────

@app.route('/api/save_exam', methods=['POST'])
def save_exam_api():
    if 'student_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401

    try:
        data = request.get_json(silent=True) or {}
        score = int(data.get('score', 0) or 0)
        total_questions = int(data.get('total', 0) or 0)
        weak_topics = data.get('weak_topics', [])
        if not isinstance(weak_topics, list):
            weak_topics = []

        unique_weak = list(dict.fromkeys(
            str(topic).strip() for topic in weak_topics if str(topic).strip()
        ))

        exam_mode = str(
            data.get('exam_mode') or session.get('exam_mode') or 'unknown'
        )
        exam_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO exam_history
                (student_id, student_name, score, total_questions, weak_topics, exam_date, is_global, subject_area)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    session['student_id'],
                    session['student_name'],
                    score,
                    total_questions,
                    '||'.join(unique_weak),
                    exam_date,
                    1 if session.get('mode') == 'global' else 0,
                    session.get('exam_topic', 'General')
                )
            )
            exam_id = cursor.lastrowid
            conn.commit()

        questions = session.get('questions') or []
        responses = data.get('question_attempts') or []

        tracked = save_question_attempts(
            get_db,
            exam_id,
            session['student_id'],
            questions,
            responses,
            exam_mode
        ) if questions else 0

        return {
            'success': True,
            'exam_id': exam_id,
            'tracked_questions': tracked
        }
    except Exception as e:
        print("ANALYTICS SAVE ERROR:", e)
        return {'success': False, 'error': str(e)}, 500


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
def profile():

    if 'student_id' not in session:
        return redirect('/login')

    sid = session['student_id']

    error = None

    success = None

    if request.method == 'POST':

        name = request.form.get(
            'name',
            ''
        ).strip()

        new_password = request.form.get(
            'new_password',
            ''
        )

        old_password = request.form.get(
            'old_password',
            ''
        )

        conn = get_db()

        student = conn.execute(
            '''
            SELECT * FROM students
            WHERE id=?
            ''',
            (sid,)
        ).fetchone()

        if student['password'] != hash_password(old_password):

            error = 'Current password is incorrect.'

        else:

            if new_password and len(new_password) < 6:

                error = (
                    'New password must be at least 6 characters.'
                )

            else:

                new_pass_hash = (
                    hash_password(new_password)
                    if new_password
                    else student['password']
                )

                conn.execute(
                    '''
                    UPDATE students
                    SET name=?, password=?
                    WHERE id=?
                    ''',
                    (
                        name,
                        new_pass_hash,
                        sid
                    )
                )

                conn.commit()

                session['student_name'] = name

                success = (
                    'Profile updated successfully!'
                )

        conn.close()

    conn = get_db()

    student = conn.execute(
        '''
        SELECT * FROM students
        WHERE id=?
        ''',
        (sid,)
    ).fetchone()

    conn.close()

    return render_template(
        'profile.html',
        student=student,
        error=error,
        success=success
    )



# ─────────────────────────────────────────────
# GLOBAL LEADERBOARD
# ─────────────────────────────────────────────

@app.route('/global_leaderboard')
def global_leaderboard():
    conn = get_db()
    
    # Calculate the total score for each student
    students = conn.execute(
        '''
        SELECT s.id, s.name, 
               COUNT(e.id) as exams_taken,
               SUM(e.score) as total_score,
               SUM(e.total_questions) as total_qs,
               GROUP_CONCAT(DISTINCT e.subject_area) as subjects
        FROM students s
        LEFT JOIN exam_history e ON s.id = e.student_id
        GROUP BY s.id
        HAVING exams_taken > 0
        ORDER BY total_score DESC, exams_taken DESC
        '''
    ).fetchall()
    
    conn.close()
    
    return render_template('global_leaderboard.html', students=students)


# ─────────────────────────────────────────────
# RUN APP
# ─────────────────────────────────────────────

if __name__ == '__main__':

    app.run(debug=True)