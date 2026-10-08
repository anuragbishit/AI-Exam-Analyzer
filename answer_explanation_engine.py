from datetime import datetime
import json


def build_ai_explanation_prompt(wrong_details):
    """Build one grounded Gemini prompt for the student's incorrect answers."""
    items = []
    for index, item in enumerate(wrong_details, 1):
        items.append(
            {
                "item_number": index,
                "question": str(item.get("question", "")).strip(),
                "your_answer": str(item.get("your_answer", "Not answered")).strip(),
                "correct_answer": str(item.get("correct_answer", "")).strip(),
                "topic": str(item.get("topic", "General")).strip(),
                "subtopic": str(item.get("subtopic", "General Concepts")).strip(),
                "options": item.get("options", []),
            }
        )

    return (
        "You are an exam tutor. Explain mistakes clearly and factually.\n"
        "Use ONLY the supplied question, answer choices, student's answer, correct answer, "
        "topic, and concept. Do not invent facts, scores, or hidden intent.\n"
        "For each incorrect answer, explain why the student's answer is incorrect, why the "
        "correct answer is correct, identify the concept being tested, and give one concise "
        "misconception to avoid.\n"
        "Keep each explanation practical and student-friendly.\n"
        "Return ONLY valid JSON with an explanations array.\n"
        "Each object must contain: item_number, explanation, concept, misconception.\n"
        "Do not include markdown fences.\n\n"
        "Questions to explain:\n"
        + json.dumps(items, ensure_ascii=False)
    )


def parse_ai_explanations(raw_text, wrong_details):
    """Validate and normalize Gemini's explanation response."""
    text = str(raw_text or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence + "json"):
        text = text[len(fence) + 4:]
    elif text.startswith(fence):
        text = text[len(fence):]
    if text.endswith(fence):
        text = text[:-len(fence)]
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("AI explanation JSON not found")

    data = json.loads(text[start:end])
    raw_items = data.get("explanations")
    if not isinstance(raw_items, list):
        raise ValueError("AI explanation response is missing explanations")

    count = min(len(wrong_details), 12)
    by_number = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("item_number"))
        except (TypeError, ValueError):
            continue
        if 1 <= number <= count:
            by_number[number] = item

    result = []
    for number in range(1, count + 1):
        source = wrong_details[number - 1]
        item = by_number.get(number)
        if not item:
            raise ValueError(f"Missing AI explanation for item {number}")

        explanation = str(item.get("explanation", "")).strip()
        concept = str(item.get("concept", "")).strip() or str(
            source.get("subtopic") or source.get("topic") or "Core Concept"
        )
        misconception = str(item.get("misconception", "")).strip()

        if not explanation:
            raise ValueError(f"Empty AI explanation for item {number}")

        result.append(
            {
                "question_index": number,
                "explanation": explanation,
                "concept": concept,
                "misconception": misconception,
                "generation_method": "gemini",
            }
        )

    return result


def build_fallback_explanations(wrong_details):
    """Provide a safe explanation when Gemini is temporarily unavailable."""
    result = []
    for index, item in enumerate(wrong_details, 1):
        your_answer = str(item.get("your_answer", "Not answered")).strip()
        correct_answer = str(item.get("correct_answer", "")).strip()
        concept = str(
            item.get("subtopic") or item.get("topic") or "Core Concept"
        ).strip()

        if your_answer.lower() == "not answered":
            explanation = (
                f"This question was left unanswered. The correct answer is "
                f"{correct_answer}. Review {concept} before attempting similar questions."
            )
            misconception = "Skipping the question leaves the concept untested."
        else:
            explanation = (
                f"Your answer, “{your_answer}”, does not match the correct answer, "
                f"“{correct_answer}”. Review {concept} and compare the definitions, rules, "
                "or steps that distinguish the two choices."
            )
            misconception = (
                f"Confusing “{your_answer}” with “{correct_answer}” is the key mistake to avoid."
            )

        result.append(
            {
                "question_index": index,
                "explanation": explanation,
                "concept": concept,
                "misconception": misconception,
                "generation_method": "rule_based_fallback",
            }
        )
    return result


def save_answer_explanations(conn, exam_id, student_id, wrong_details, explanations):
    """Persist explanations for later analytics and display."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    by_index = {int(item["question_index"]): item for item in explanations}
    for index, source in enumerate(wrong_details, 1):
        generated = by_index.get(index)
        if not generated:
            continue
        rows.append(
            (
                exam_id,
                student_id,
                index,
                str(source.get("question", "")).strip(),
                str(source.get("your_answer", "Not answered")).strip(),
                str(source.get("correct_answer", "")).strip(),
                str(source.get("topic", "General")).strip() or "General",
                str(source.get("subtopic", "General Concepts")).strip() or "General Concepts",
                generated["explanation"],
                generated["concept"],
                generated["misconception"],
                generated["generation_method"],
                now,
            )
        )

    if rows:
        conn.execute(
            "DELETE FROM answer_explanations WHERE exam_id=? AND student_id=?",
            (exam_id, student_id),
        )
        conn.executemany(
            """
            INSERT INTO answer_explanations
            (exam_id, student_id, question_index, question_text,
             selected_answer, correct_answer, topic, subtopic,
             explanation, concept, misconception, generation_method, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def get_answer_explanations(conn, exam_id, student_id):
    """Fetch persisted explanations belonging to the authenticated student."""
    return conn.execute(
        """
        SELECT question_index, question_text, selected_answer, correct_answer,
               topic, subtopic, explanation, concept, misconception, generation_method
        FROM answer_explanations
        WHERE exam_id=? AND student_id=?
        ORDER BY question_index ASC
        """,
        (exam_id, student_id),
    ).fetchall()
