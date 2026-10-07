from datetime import datetime, timedelta


DEFAULT_DAYS = 7


def build_ai_study_plan_prompt(topic_mastery, knowledge_gaps, days=7):
    """Create a grounded Gemini prompt using only the student's analytics."""
    gap_lines = []
    for gap in (knowledge_gaps or {}).get("gaps", [])[:8]:
        gap_lines.append(
            "- Topic: {topic} | Concept: {subtopic} | Mastery: {mastery}% | "
            "Accuracy: {accuracy}% | Recent: {recent}% | Attempts: {attempts} | "
            "Avg Time: {time}s | Gap: {level} | Signals: {signals}".format(
                topic=gap.get("topic", "General"),
                subtopic=gap.get("subtopic", "Core Concepts"),
                mastery=gap.get("mastery", 0),
                accuracy=gap.get("accuracy", 0),
                recent=gap.get("recent_accuracy", 0),
                attempts=gap.get("attempts", 0),
                time=gap.get("avg_response_time", 0),
                level=gap.get("gap_level", "Watch"),
                signals=", ".join(gap.get("reasons", [])) or "below target"
            )
        )

    mastery_lines = []
    for item in (topic_mastery or [])[:10]:
        mastery_lines.append(
            "- Topic: {topic} | Mastery: {mastery}% | Accuracy: {accuracy}% | Attempts: {attempts}".format(
                topic=item.get("topic", "General"),
                mastery=item.get("mastery_score", 0),
                accuracy=item.get("accuracy", 0),
                attempts=item.get("attempts", 0)
            )
        )

    return (
        "You are an educational planning assistant.\n"
        f"Create a personalized {days}-day study plan ONLY from the supplied student analytics.\n"
        "Do not invent unsupported subjects, topics, concepts, scores, or diagnoses.\n\n"
        "Prioritize Critical/High knowledge gaps, then weak/developing topics.\n"
        f"Day {days} must be a cumulative final assessment.\n\n"
        f"Return ONLY valid JSON with exactly {days} objects in the days array.\n"
        "Each day must contain: day_number, title, topic, subtopic, priority, "
        "recommended_minutes, learning_objective, practice_questions.\n"
        "priority must be one of Critical, High, Medium, Low, Assessment.\n"
        "recommended_minutes must be an integer from 15 to 60.\n"
        "practice_questions must be an integer from 5 to 20.\n"
        "Use specific actionable objectives and do not repeat the same objective.\n"
        f"Day {days} must have priority Assessment.\n\n"
        "JSON shape:\n"
        "{\n"
        "  \"title\": \"AI Personalized Study Plan\",\n"
        "  \"days\": [\n"
        "    {\n"
        "      \"day_number\": 1,\n"
        "      \"title\": \"Focused Concept Review\",\n"
        "      \"topic\": \"Database Systems\",\n"
        "      \"subtopic\": \"Normalization\",\n"
        "      \"priority\": \"Critical\",\n"
        "      \"recommended_minutes\": 45,\n"
        "      \"learning_objective\": \"Review the identified concept and summarize its key rules.\",\n"
        "      \"practice_questions\": 12\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Knowledge gaps:\n"
        + ("\n".join(gap_lines) if gap_lines else "- No confirmed gaps yet.")
        + "\n\nTopic mastery:\n"
        + ("\n".join(mastery_lines) if mastery_lines else "- No mastery data yet.")
    )


def parse_ai_study_plan(raw_text, topic_mastery, knowledge_gaps, days=7):
    """Validate Gemini's structured plan before persistence."""
    import json

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
        raise ValueError("AI study plan JSON not found")

    data = json.loads(text[start:end])
    raw_days = data.get("days")
    if not isinstance(raw_days, list) or len(raw_days) != days:
        raise ValueError("AI returned an invalid number of study-plan days")

    allowed_topics = {
        str(item.get("topic", "")).strip().lower(): str(item.get("topic", "")).strip()
        for item in (topic_mastery or [])
        if str(item.get("topic", "")).strip()
    }
    for gap in (knowledge_gaps or {}).get("all_concepts", []):
        topic = str(gap.get("topic", "")).strip()
        if topic:
            allowed_topics[topic.lower()] = topic

    result = []
    for expected, item in enumerate(raw_days, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid day {expected}")

        try:
            day_number = int(item.get("day_number", expected))
            minutes = int(item.get("recommended_minutes", 30))
            practice = int(item.get("practice_questions", 10))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid numeric values on day {expected}")

        if day_number != expected:
            raise ValueError(f"Study-plan day sequence is invalid at day {expected}")
        if not 15 <= minutes <= 60:
            raise ValueError(f"Study time out of range on day {expected}")
        if not 5 <= practice <= 20:
            raise ValueError(f"Practice count out of range on day {expected}")

        title = str(item.get("title", "")).strip() or f"Day {expected} Focus"
        topic = str(item.get("topic", "")).strip() or "General Revision"
        subtopic = str(item.get("subtopic", "")).strip() or topic
        priority = str(item.get("priority", "Medium")).strip().title()
        objective = str(item.get("learning_objective", "")).strip()

        if priority not in {"Critical", "High", "Medium", "Low", "Assessment"}:
            priority = "Medium"

        if expected != days and allowed_topics and topic.lower() not in allowed_topics:
            topic = sorted(allowed_topics.values())[0]
            subtopic = "Core Concepts"

        if expected == days:
            title = title or "Final Assessment"
            topic = "Final Assessment"
            subtopic = "Mixed Weak-Area Review"
            priority = "Assessment"
            minutes = max(minutes, 35)
            practice = max(practice, 15)

        if not objective:
            objective = f"Study and practice {subtopic} using targeted questions."

        result.append({
            "day_number": expected,
            "title": title,
            "topic": topic,
            "subtopic": subtopic,
            "priority": priority,
            "recommended_minutes": minutes,
            "objective": objective,
            "practice_questions": practice,
            "status": "pending",
            "reason": "AI personalized from current performance data"
        })

    return {
        "title": str(data.get("title", "")).strip() or "AI Personalized Study Plan",
        "duration_days": days,
        "status": "active",
        "generation_method": "gemini",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": result
    }


def build_draft_study_plan(topic_mastery, knowledge_gaps, days=DEFAULT_DAYS):
    """
    Build a deterministic study plan from the current student analytics.

    This is intentionally non-generative for Step 6A. The plan is driven by
    confirmed knowledge gaps first, then developing/weak topics, then review.
    """
    days = max(1, min(int(days), 30))

    gaps = (knowledge_gaps or {}).get("gaps", [])
    mastery = topic_mastery or []

    candidates = []

    for gap in gaps:
        candidates.append({
            "topic": gap["topic"],
            "subtopic": gap["subtopic"],
            "priority": (
                "Critical" if gap.get("gap_level") == "Critical"
                else "High" if gap.get("gap_level") == "High"
                else "Watch"
            ),
            "mastery": gap.get("mastery", 0),
            "attempts": gap.get("attempts", 0),
            "base_minutes": 40 if gap.get("mastery", 0) < 40 else 30,
            "reason": ", ".join(gap.get("reasons", [])) or "below target mastery"
        })

    seen = {(item["topic"].lower(), item["subtopic"].lower()) for item in candidates}

    # Add the weakest non-gap mastery areas as supporting study items.
    for item in sorted(
        mastery,
        key=lambda x: (x.get("mastery_score", 100), -x.get("attempts", 0))
    ):
        key = (item["topic"].lower(), item.get("subtopic", item["topic"]).lower())
        if key in seen:
            continue

        if item.get("mastery_score", 100) < 75:
            candidates.append({
                "topic": item["topic"],
                "subtopic": item["topic"],
                "priority": "Medium",
                "mastery": item.get("mastery_score", 0),
                "attempts": item.get("attempts", 0),
                "base_minutes": 25,
                "reason": "developing topic mastery"
            })
            seen.add(key)

    if not candidates:
        candidates.append({
            "topic": "General Revision",
            "subtopic": "Mixed Practice",
            "priority": "Medium",
            "mastery": 100,
            "attempts": 0,
            "base_minutes": 25,
            "reason": "build a baseline through mixed practice"
        })

    plan_items = []

    for day in range(1, days + 1):
        if day == days:
            primary = None
            objective = "Measure improvement across previously identified weak areas."
            topic = "Final Assessment"
            subtopic = "Mixed Weak-Area Review"
            priority = "Assessment"
            minutes = 40
            practice_count = 15
        else:
            primary = candidates[(day - 1) % len(candidates)]
            topic = primary["topic"]
            subtopic = primary["subtopic"]
            priority = primary["priority"]
            minutes = primary["base_minutes"]

            if day == 1:
                objective = f"Build a strong foundation in {subtopic}."
            elif day == 2:
                objective = f"Practice the core patterns and common problems in {subtopic}."
            elif day % 3 == 0:
                objective = f"Review {subtopic} and test recall with targeted questions."
            else:
                objective = f"Improve accuracy and confidence in {subtopic}."

            practice_count = max(5, round(minutes / 3))

        plan_items.append({
            "day_number": day,
            "topic": topic,
            "subtopic": subtopic,
            "priority": priority,
            "recommended_minutes": minutes,
            "objective": objective,
            "practice_questions": practice_count,
            "status": "pending",
            "reason": primary["reason"] if primary else "final progress check"
        })

    now = datetime.now()
    return {
        "title": "AI Personalized Study Plan",
        "duration_days": days,
        "status": "draft",
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "items": plan_items
    }


def save_study_plan(conn, student_id, plan):
    """Persist a draft plan and return its database id."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO study_plans
        (student_id, title, duration_days, status, generation_method, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            plan["title"],
            plan["duration_days"],
            plan.get("status", "draft"),
            plan.get("generation_method", "rule_based"),
            now,
            now
        )
    )
    plan_id = cursor.lastrowid

    for item in plan["items"]:
        cursor.execute(
            """
            INSERT INTO study_plan_items
            (plan_id, day_number, topic, subtopic, priority,
             recommended_minutes, objective, practice_questions,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                item["day_number"],
                item.get("title", f"Day {item['day_number']} Focus"),
                item["topic"],
                item["subtopic"],
                item["priority"],
                item["recommended_minutes"],
                item["objective"],
                item["practice_questions"],
                item["status"],
                now
            )
        )

    conn.commit()
    return plan_id

def get_active_study_plan(conn, student_id):
    """Return the latest active or draft plan with its items."""
    plan = conn.execute(
        """
        SELECT *
        FROM study_plans
        WHERE student_id=? AND status IN ('active', 'draft')
        ORDER BY id DESC
        LIMIT 1
        """,
        (student_id,)
    ).fetchone()

    if not plan:
        return None

    items = conn.execute(
        """
        SELECT *
        FROM study_plan_items
        WHERE plan_id=?
        ORDER BY day_number ASC
        """,
        (plan["id"],)
    ).fetchall()

    completed = sum(1 for item in items if item["status"] == "completed")

    return {
        "id": plan["id"],
        "title": plan["title"],
        "duration_days": plan["duration_days"],
        "status": plan["status"],
        "created_at": plan["created_at"],
        "updated_at": plan["updated_at"],
        "completed_items": completed,
        "total_items": len(items),
        "progress_percent": round((completed / len(items)) * 100) if items else 0,
        "items": items
    }


def toggle_plan_item(conn, student_id, item_id):
    """Toggle one item between pending and completed."""
    row = conn.execute(
        """
        SELECT spi.id, spi.plan_id, spi.status
        FROM study_plan_items spi
        JOIN study_plans sp ON sp.id = spi.plan_id
        WHERE spi.id=? AND sp.student_id=?
        """,
        (item_id, student_id)
    ).fetchone()

    if not row:
        return False

    new_status = "pending" if row["status"] == "completed" else "completed"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    completed_at = now if new_status == "completed" else None

    conn.execute(
        """
        UPDATE study_plan_items
        SET status=?, completed_at=?
        WHERE id=?
        """,
        (new_status, completed_at, item_id)
    )

    remaining = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM study_plan_items
        WHERE plan_id=? AND status!='completed'
        """,
        (row["plan_id"],)
    ).fetchone()["count"]

    plan_status = "completed" if remaining == 0 else "active"

    conn.execute(
        """
        UPDATE study_plans
        SET status=?, updated_at=?
        WHERE id=?
        """,
        (plan_status, now, row["plan_id"])
    )
    conn.commit()
    return True
