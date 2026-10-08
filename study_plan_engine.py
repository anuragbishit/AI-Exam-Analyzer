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




def build_ai_adaptive_study_plan_prompt(active_plan, topic_mastery, knowledge_gaps):
    """Build a grounded Gemini prompt for adapting only unfinished plan days."""
    pending = [
        dict(item)
        for item in (active_plan or {}).get("items", [])
        if item.get("status") != "completed"
    ]
    if not pending:
        raise ValueError("There are no pending study-plan days to adapt")

    pending_lines = []
    for item in pending:
        pending_lines.append(
            "- Day {day}: {title} | Topic: {topic} | Concept: {subtopic} | "
            "Priority: {priority} | Minutes: {minutes} | Practice: {practice}".format(
                day=item.get("day_number"),
                title=item.get("title", f"Day {item.get('day_number')} Focus"),
                topic=item.get("topic", "General"),
                subtopic=item.get("subtopic", "Core Concepts"),
                priority=item.get("priority", "Medium"),
                minutes=item.get("recommended_minutes", 30),
                practice=item.get("practice_questions", 10)
            )
        )

    gap_lines = []
    for gap in (knowledge_gaps or {}).get("gaps", [])[:8]:
        gap_lines.append(
            "- Topic: {topic} | Concept: {subtopic} | Mastery: {mastery}% | "
            "Accuracy: {accuracy}% | Recent: {recent}% | Attempts: {attempts} | "
            "Gap: {level} | Signals: {signals}".format(
                topic=gap.get("topic", "General"),
                subtopic=gap.get("subtopic", "Core Concepts"),
                mastery=gap.get("mastery", 0),
                accuracy=gap.get("accuracy", 0),
                recent=gap.get("recent_accuracy", 0),
                attempts=gap.get("attempts", 0),
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

    pending_count = len(pending)
    final_day = active_plan.get("duration_days", 7)

    return (
        "You are an adaptive educational planning assistant.\n"
        "Adapt ONLY the unfinished days in the existing study plan.\n"
        "Completed days are locked and must never be changed.\n"
        "Use only the supplied performance analytics and existing plan topics.\n"
        "Prioritize newly confirmed Critical/High knowledge gaps and declining recent performance.\n"
        f"Return ONLY valid JSON with exactly {pending_count} objects in the days array.\n"
        "Every day_number must exactly match one of the pending day numbers supplied below.\n"
        "Each object must contain: day_number, title, topic, subtopic, priority, "
        "recommended_minutes, learning_objective, practice_questions.\n"
        "priority must be one of Critical, High, Medium, Low, Assessment.\n"
        "recommended_minutes must be an integer from 15 to 60.\n"
        "practice_questions must be an integer from 5 to 20.\n"
        f"Day {final_day}, when it is still pending, must remain the cumulative final assessment.\n"
        "Do not invent unsupported topics or concepts. Do not duplicate the same objective.\n\n"
        "Existing pending plan days:\n"
        + "\n".join(pending_lines)
        + "\n\nCurrent knowledge gaps:\n"
        + ("\n".join(gap_lines) if gap_lines else "- No confirmed gaps yet.")
        + "\n\nCurrent topic mastery:\n"
        + ("\n".join(mastery_lines) if mastery_lines else "- No mastery data yet.")
    )


def parse_ai_adaptive_study_plan(raw_text, active_plan, topic_mastery, knowledge_gaps):
    """Validate Gemini's adaptive plan and preserve the existing day sequence."""
    import json

    pending = [
        dict(item)
        for item in (active_plan or {}).get("items", [])
        if item.get("status") != "completed"
    ]
    expected_days = [int(item.get("day_number")) for item in pending]
    if not expected_days:
        raise ValueError("No pending study-plan days are available")

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
        raise ValueError("AI adaptive study plan JSON not found")

    data = json.loads(text[start:end])
    raw_days = data.get("days")
    if not isinstance(raw_days, list) or len(raw_days) != len(expected_days):
        raise ValueError("AI returned an invalid number of adaptive days")

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
    for index, item in enumerate(raw_days):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid adaptive day {expected_days[index]}")

        expected_day = expected_days[index]
        try:
            day_number = int(item.get("day_number"))
            minutes = int(item.get("recommended_minutes", 30))
            practice = int(item.get("practice_questions", 10))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid numeric values on day {expected_day}")

        if day_number != expected_day:
            raise ValueError(f"Adaptive day sequence is invalid at day {expected_day}")
        if not 15 <= minutes <= 60:
            raise ValueError(f"Study time out of range on day {expected_day}")
        if not 5 <= practice <= 20:
            raise ValueError(f"Practice count out of range on day {expected_day}")

        title = str(item.get("title", "")).strip() or f"Day {expected_day} Focus"
        topic = str(item.get("topic", "")).strip() or "General Revision"
        subtopic = str(item.get("subtopic", "")).strip() or topic
        priority = str(item.get("priority", "Medium")).strip().title()
        objective = str(item.get("learning_objective", "")).strip()

        if priority not in {"Critical", "High", "Medium", "Low", "Assessment"}:
            priority = "Medium"

        if allowed_topics and topic.lower() not in allowed_topics and expected_day != int(active_plan.get("duration_days", 7)):
            topic = sorted(allowed_topics.values())[0]
            subtopic = "Core Concepts"

        if expected_day == int(active_plan.get("duration_days", 7)):
            title = title or "Final Assessment"
            topic = "Final Assessment"
            subtopic = "Mixed Weak-Area Review"
            priority = "Assessment"
            minutes = max(minutes, 35)
            practice = max(practice, 15)

        if not objective:
            objective = f"Review and practice {subtopic} using the latest performance signals."

        result.append({
            "day_number": expected_day,
            "title": title,
            "topic": topic,
            "subtopic": subtopic,
            "priority": priority,
            "recommended_minutes": minutes,
            "objective": objective,
            "practice_questions": practice,
            "reason": "AI adapted from the latest performance data"
        })

    return result


def build_adaptive_fallback_items(active_plan, topic_mastery, knowledge_gaps):
    """Fast deterministic adaptation used after an exam or Gemini failure."""
    pending = [
        dict(item)
        for item in (active_plan or {}).get("items", [])
        if item.get("status") != "completed"
    ]

    gaps = list((knowledge_gaps or {}).get("gaps", []))
    candidates = []

    for gap in gaps:
        candidates.append({
            "topic": gap.get("topic", "General"),
            "subtopic": gap.get("subtopic", gap.get("topic", "General")),
            "priority": (
                "Critical" if gap.get("gap_level") == "Critical"
                else "High" if gap.get("gap_level") == "High"
                else "Medium"
            ),
            "mastery": gap.get("mastery", 0),
            "reason": ", ".join(gap.get("reasons", [])) or "latest performance shows room for improvement"
        })

    seen = {(c["topic"].lower(), c["subtopic"].lower()) for c in candidates}
    for item in sorted(
        topic_mastery or [],
        key=lambda x: (x.get("mastery_score", 100), -x.get("attempts", 0))
    ):
        topic = str(item.get("topic", "General")).strip() or "General"
        subtopic = str(item.get("subtopic", topic)).strip() or topic
        key = (topic.lower(), subtopic.lower())
        if key in seen:
            continue
        if item.get("mastery_score", 100) < 75:
            candidates.append({
                "topic": topic,
                "subtopic": subtopic,
                "priority": "Medium",
                "mastery": item.get("mastery_score", 0),
                "reason": "latest mastery remains below the target range"
            })
            seen.add(key)

    result = []
    for index, old_item in enumerate(pending):
        day = int(old_item["day_number"])

        if day == int((active_plan or {}).get("duration_days", 7)):
            result.append({
                "day_number": day,
                "title": "Cumulative Final Assessment",
                "topic": "Final Assessment",
                "subtopic": "Mixed Weak-Area Review",
                "priority": "Assessment",
                "recommended_minutes": 40,
                "objective": "Measure improvement across the latest identified weak areas.",
                "practice_questions": 15,
                "reason": "final progress check after the latest performance update"
            })
            continue

        if candidates:
            primary = candidates[index % len(candidates)]
            minutes = 40 if primary["mastery"] < 40 else 30
            practice = max(5, min(20, round(minutes / 3)))
            objective = (
                f"Rebuild confidence in {primary['subtopic']} and correct the latest weak signals."
                if primary["priority"] in {"Critical", "High"}
                else f"Strengthen accuracy and recall in {primary['subtopic']}."
            )
            result.append({
                "day_number": day,
                "title": f"Adaptive Focus: {primary['subtopic']}",
                "topic": primary["topic"],
                "subtopic": primary["subtopic"],
                "priority": primary["priority"],
                "recommended_minutes": minutes,
                "objective": objective,
                "practice_questions": practice,
                "reason": primary["reason"]
            })
        else:
            result.append({
                "day_number": day,
                "title": old_item.get("title", f"Day {day} Focus"),
                "topic": old_item.get("topic", "General Revision"),
                "subtopic": old_item.get("subtopic", "Mixed Practice"),
                "priority": old_item.get("priority", "Medium"),
                "recommended_minutes": int(old_item.get("recommended_minutes", 30)),
                "objective": "Continue the planned revision using the newest performance feedback.",
                "practice_questions": int(old_item.get("practice_questions", 10)),
                "reason": "no stronger confirmed gap was detected"
            })

    return result


def adapt_study_plan(conn, student_id, plan_id, adapted_items, generation_method, reason, trigger_type="exam_completed"):
    """Update only pending items and log the adaptation event."""
    plan_row = conn.execute(
        """
        SELECT *
        FROM study_plans
        WHERE id=? AND student_id=?
        """,
        (plan_id, student_id)
    ).fetchone()

    if not plan_row:
        raise ValueError("Study plan not found")

    current_items = conn.execute(
        """
        SELECT *
        FROM study_plan_items
        WHERE plan_id=?
        ORDER BY day_number ASC
        """,
        (plan_id,)
    ).fetchall()

    current_by_day = {int(item["day_number"]): item for item in current_items}
    updated_days = []

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in adapted_items:
        day = int(item["day_number"])
        current = current_by_day.get(day)
        if not current:
            continue
        if current["status"] == "completed":
            continue

        conn.execute(
            """
            UPDATE study_plan_items
            SET title=?, topic=?, subtopic=?, priority=?,
                recommended_minutes=?, objective=?, practice_questions=?
            WHERE id=?
            """,
            (
                item.get("title", f"Day {day} Focus"),
                item.get("topic", "General Revision"),
                item.get("subtopic", "Mixed Practice"),
                item.get("priority", "Medium"),
                int(item.get("recommended_minutes", 30)),
                item.get("objective", "Continue targeted revision."),
                int(item.get("practice_questions", 10)),
                current["id"]
            )
        )
        updated_days.append(day)

    conn.execute(
        """
        UPDATE study_plans
        SET generation_method=?, adaptation_count=COALESCE(adaptation_count, 0)+1,
            last_adapted_at=?, last_adaptation_reason=?, updated_at=?
        WHERE id=? AND student_id=?
        """,
        (
            generation_method,
            now,
            reason,
            now,
            plan_id,
            student_id
        )
    )

    conn.execute(
        """
        INSERT INTO study_plan_adaptations
        (plan_id, student_id, trigger_type, generation_method,
         changed_days, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            student_id,
            trigger_type,
            generation_method,
            ",".join(str(day) for day in updated_days),
            reason,
            now
        )
    )

    conn.commit()
    return updated_days


def auto_adapt_active_study_plan(conn, student_id, reason="New exam performance detected"):
    """Automatically adapt pending days after fresh question-level analytics."""
    plan = get_active_study_plan(conn, student_id)
    if not plan or not plan.get("items"):
        return {"adapted": False, "reason": "no active plan"}

    pending = [item for item in plan["items"] if item["status"] != "completed"]
    if not pending:
        return {"adapted": False, "reason": "plan already completed"}

    topic_mastery = calculate_topic_mastery_from_connection(conn, student_id)
    knowledge_gaps = calculate_knowledge_gaps_from_connection(conn, student_id)

    adapted_items = build_adaptive_fallback_items(
        plan,
        topic_mastery,
        knowledge_gaps
    )

    updated_days = adapt_study_plan(
        conn,
        student_id,
        plan["id"],
        adapted_items,
        "rule_based_auto_adaptive",
        reason
    )

    return {
        "adapted": bool(updated_days),
        "generation_method": "rule_based_auto_adaptive",
        "changed_days": updated_days
    }


def calculate_topic_mastery_from_connection(conn, student_id):
    from mastery_engine import calculate_topic_mastery
    return calculate_topic_mastery(conn, student_id)


def calculate_knowledge_gaps_from_connection(conn, student_id):
    from knowledge_gap_engine import calculate_knowledge_gaps
    return calculate_knowledge_gaps(conn, student_id)


def get_recent_plan_adaptations(conn, student_id, plan_id, limit=5):
    """Return recent adaptation events for the current plan."""
    rows = conn.execute(
        """
        SELECT id, trigger_type, generation_method, changed_days, reason, created_at
        FROM study_plan_adaptations
        WHERE student_id=? AND plan_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (student_id, plan_id, int(limit))
    ).fetchall()
    return rows


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
            (plan_id, day_number, title, topic, subtopic, priority,
             recommended_minutes, objective, practice_questions,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        "generation_method": plan["generation_method"] if "generation_method" in plan.keys() else "rule_based",
        "adaptation_count": plan["adaptation_count"] if "adaptation_count" in plan.keys() else 0,
        "last_adapted_at": plan["last_adapted_at"] if "last_adapted_at" in plan.keys() else None,
        "last_adaptation_reason": plan["last_adaptation_reason"] if "last_adaptation_reason" in plan.keys() else None,
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
