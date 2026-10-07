def calculate_knowledge_gaps(conn, student_id):
    """
    Detect concept-level knowledge gaps from question_attempts.

    The score is deliberately transparent:
      - 70% historical accuracy
      - 30% recent accuracy (latest five attempts)
    A time warning is added when a concept is consistently much slower than
    the student's overall question response time.

    Concepts with too little data are marked as low-confidence instead of
    being incorrectly treated as a confirmed weakness.
    """
    rows = conn.execute(
        """
        SELECT id, topic, subtopic, is_correct, response_time_seconds
        FROM question_attempts
        WHERE student_id=?
        ORDER BY id ASC
        """,
        (student_id,)
    ).fetchall()

    concepts = {}

    for row in rows:
        topic = str(row["topic"] or "General").strip() or "General"
        subtopic = str(row["subtopic"] or topic).strip() or topic

        # Avoid treating the generic fallback as a separate meaningful
        # concept when older records have no real subtopic.
        if subtopic.lower() == "general concepts" and topic:
            subtopic = "General Concepts"

        key = (topic, subtopic)
        if key not in concepts:
            concepts[key] = {
                "topic": topic,
                "subtopic": subtopic,
                "results": [],
                "times": []
            }

        item = concepts[key]
        item["results"].append(int(row["is_correct"] or 0))

        try:
            item["times"].append(
                max(0.0, float(row["response_time_seconds"] or 0))
            )
        except (TypeError, ValueError):
            pass

    all_times = [
        t
        for item in concepts.values()
        for t in item["times"]
        if t > 0
    ]
    overall_avg_time = (
        sum(all_times) / len(all_times)
        if all_times else 0
    )

    gaps = []

    for (topic, subtopic), item in concepts.items():
        attempts = len(item["results"])
        correct = sum(item["results"])
        accuracy = (correct / attempts) * 100 if attempts else 0

        recent = item["results"][-5:]
        recent_accuracy = (
            (sum(recent) / len(recent)) * 100
            if recent else accuracy
        )

        mastery = (
            (accuracy * 0.70) + (recent_accuracy * 0.30)
            if attempts >= 3 else accuracy
        )

        avg_time = (
            sum(item["times"]) / len(item["times"])
            if item["times"] else 0
        )

        slow_response = bool(
            overall_avg_time > 0
            and avg_time > overall_avg_time * 1.35
            and attempts >= 2
        )

        reasons = []
        if accuracy < 60:
            reasons.append("low accuracy")
        if attempts >= 3 and recent_accuracy + 15 < accuracy:
            reasons.append("recent performance is declining")
        if slow_response:
            reasons.append("response time is high")

        # Confirmed gap only when there is meaningful evidence.
        confirmed_gap = attempts >= 2 and (mastery < 60 or len(reasons) >= 2)

        if confirmed_gap:
            gap_level = "Critical" if mastery < 40 else "High" if mastery < 60 else "Watch"
        else:
            gap_level = "Low"

        if attempts < 2:
            confidence = "Low confidence"
        elif attempts < 5:
            confidence = "Emerging"
        else:
            confidence = "High confidence"

        gaps.append({
            "topic": topic,
            "subtopic": subtopic,
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(accuracy),
            "recent_accuracy": round(recent_accuracy),
            "mastery": round(mastery),
            "avg_response_time": round(avg_time, 1),
            "gap_level": gap_level,
            "confidence": confidence,
            "reasons": reasons,
            "is_gap": confirmed_gap
        })

    # Show confirmed gaps first, then watch items, while keeping all concepts
    # available for later analytics.
    gaps.sort(
        key=lambda item: (
            not item["is_gap"],
            item["mastery"],
            -item["attempts"],
            item["subtopic"].lower()
        )
    )

    confirmed = [g for g in gaps if g["is_gap"]]
    return {
        "all_concepts": gaps,
        "gaps": confirmed[:8],
        "overall_avg_time": round(overall_avg_time, 1)
    }


def build_knowledge_gap_prompt(gap_data):
    """Build a compact, grounded prompt for an optional AI diagnosis."""
    gaps = gap_data.get("gaps", [])
    if not gaps:
        return None

    lines = []
    for gap in gaps[:5]:
        reason = ", ".join(gap["reasons"]) or "below target mastery"
        lines.append(
            f"- Topic: {gap['topic']} | Concept: {gap['subtopic']} | "
            f"Accuracy: {gap['accuracy']}% | Recent: {gap['recent_accuracy']}% | "
            f"Attempts: {gap['attempts']} | Avg time: {gap['avg_response_time']}s | "
            f"Signals: {reason}"
        )

    return """You are an educational performance analyst.
Use ONLY the supplied student analytics. Do not invent facts.

Identify the student's most important concept-level knowledge gaps.
For each gap, provide:
1. Likely learning issue suggested by the data (not a medical or psychological diagnosis).
2. What concept to revise.
3. One concrete practice action.

Keep the answer concise and practical. Return plain text with one numbered section per gap.

Student analytics:
""" + "\n".join(lines)
