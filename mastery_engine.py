def calculate_topic_mastery(conn, student_id):
    """
    Calculate a transparent topic mastery score from question-level attempts.

    Overall accuracy gives the long-term baseline. When a topic has at least
    three attempts, recent accuracy (last five attempts) is blended in so an
    improving student is rewarded without discarding historical performance.
    """
    rows = conn.execute(
        """
        SELECT topic, is_correct, response_time_seconds
        FROM question_attempts
        WHERE student_id=?
        ORDER BY id ASC
        """,
        (student_id,)
    ).fetchall()

    topics = {}

    for row in rows:
        topic = str(row["topic"] or "General").strip() or "General"

        if topic not in topics:
            topics[topic] = {
                "attempts": 0,
                "correct": 0,
                "times": [],
                "recent_results": []
            }

        item = topics[topic]
        correct = int(row["is_correct"] or 0)
        item["attempts"] += 1
        item["correct"] += correct
        item["recent_results"].append(correct)

        try:
            item["times"].append(max(0.0, float(row["response_time_seconds"] or 0)))
        except (TypeError, ValueError):
            pass

    mastery = []

    for topic, item in topics.items():
        attempts = item["attempts"]
        accuracy = (item["correct"] / attempts) * 100 if attempts else 0

        recent = item["recent_results"][-5:]
        recent_accuracy = (
            (sum(recent) / len(recent)) * 100
            if recent else accuracy
        )

        if attempts >= 3:
            mastery_score = (accuracy * 0.70) + (recent_accuracy * 0.30)
        else:
            mastery_score = accuracy

        mastery_score = round(mastery_score)

        if mastery_score >= 90:
            status = "Mastered"
        elif mastery_score >= 75:
            status = "Strong"
        elif mastery_score >= 60:
            status = "Developing"
        elif mastery_score >= 40:
            status = "Weak"
        else:
            status = "Critical"

        if attempts < 3:
            confidence = "Early signal"
        elif attempts < 6:
            confidence = "Building confidence"
        else:
            confidence = "Reliable"

        avg_time = (
            sum(item["times"]) / len(item["times"])
            if item["times"] else 0
        )

        mastery.append({
            "topic": topic,
            "attempts": attempts,
            "correct": item["correct"],
            "accuracy": round(accuracy),
            "recent_accuracy": round(recent_accuracy),
            "mastery_score": mastery_score,
            "avg_response_time": round(avg_time, 1),
            "status": status,
            "confidence": confidence
        })

    mastery.sort(key=lambda item: (-item["mastery_score"], -item["attempts"], item["topic"].lower()))
    return mastery
