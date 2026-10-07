import sqlite3
from datetime import datetime

def ensure_question_attempts_table(get_db):
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS question_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                question_index INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                topic TEXT DEFAULT 'General',
                subtopic TEXT DEFAULT 'General Concepts',
                difficulty TEXT DEFAULT 'custom',
                selected_answer TEXT,
                correct_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL DEFAULT 0,
                response_time_seconds REAL DEFAULT 0,
                exam_mode TEXT DEFAULT 'unknown',
                attempted_at TEXT NOT NULL
            )
        """)

        # Backward-compatible migration for databases created before Step 5A.
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(question_attempts)").fetchall()
        }
        if "subtopic" not in columns:
            conn.execute(
                "ALTER TABLE question_attempts ADD COLUMN subtopic TEXT DEFAULT 'General Concepts'"
            )

        conn.commit()

def save_question_attempts(get_db, exam_id, student_id, questions, responses, exam_mode):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = []
    for index, q in enumerate(questions):
        response = responses[index] if index < len(responses) and isinstance(responses[index], dict) else {}
        selected_index = response.get('selected_index')
        selected_answer = None
        try:
            if selected_index is not None:
                selected_index = int(selected_index)
                if 0 <= selected_index < len(q.get('options', [])):
                    selected_answer = str(q['options'][selected_index])
        except (TypeError, ValueError):
            selected_index = None

        correct_answer = str(q.get('answer', '')).strip()
        is_correct = int(selected_answer is not None and selected_answer == correct_answer)
        try:
            response_time = max(0.0, float(response.get('response_time_seconds', 0) or 0))
        except (TypeError, ValueError):
            response_time = 0.0

        rows.append((
            exam_id,
            student_id,
            index + 1,
            str(q.get('question', '')).strip(),
            str(q.get('topic', 'General')).strip() or 'General',
            str(q.get('subtopic', 'General Concepts')).strip() or 'General Concepts',
            str(q.get('difficulty', 'custom')).strip() or 'custom',
            selected_answer,
            correct_answer,
            is_correct,
            round(response_time, 2),
            exam_mode,
            now
        ))

    with get_db() as conn:
        conn.executemany("""
            INSERT INTO question_attempts
            (exam_id, student_id, question_index, question_text, topic, subtopic, difficulty,
             selected_answer, correct_answer, is_correct, response_time_seconds,
             exam_mode, attempted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
    return len(rows)
