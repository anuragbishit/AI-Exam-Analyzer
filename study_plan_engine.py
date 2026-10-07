from datetime import datetime, timedelta


DEFAULT_DAYS = 7


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
        key = (item["topic"].lower(), item["topic"].lower())
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
        (student_id, title, duration_days, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            plan["title"],
            plan["duration_days"],
            plan["status"],
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
