"""Groq-powered Q&A grounded in the loaded campus CSV data.

Only aggregate metrics and a small, query-relevant set of de-identified student
records are sent to Groq. Names, IDs, and email addresses are substituted
locally and restored only in the API response for authorized staff users.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import httpx
import pandas as pd
from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..data_service import DataService
from ..deps import get_service
from ..utils import success

logger = logging.getLogger("smart_campus.ai")
router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
ALLOWED_ROLES = {"admin", "faculty", "placement_officer", "judge_demo"}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a question before sending.")
        return value.strip()

    @field_validator("history")
    @classmethod
    def validate_history(cls, values: list[str]) -> list[str]:
        return [str(v).strip()[:1500] for v in values[-8:] if str(v).strip()]


def _clean_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        return value
    return str(value)


def _mean(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return round(float(values.mean()), 2) if len(values) else None


def _value_counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[column].fillna("Not recorded").value_counts().items()}


def _skill_name_matches(query: str, skill_name: str) -> list[tuple[int, int]]:
    suffix = r"(?![A-Za-z0-9+#])" if skill_name.casefold() == "c" else r"(?![A-Za-z0-9])"
    pattern = r"(?<![A-Za-z0-9])" + re.escape(skill_name) + suffix
    return [match.span() for match in re.finditer(pattern, query, flags=re.IGNORECASE)]


def _skill_query_rows(service: DataService, query: str) -> list[dict] | None:
    skills = getattr(service, "student_skills", pd.DataFrame())
    skill_col, id_col = "Skill Name", "Student ID"
    if skills.empty or skill_col not in skills.columns or id_col not in skills.columns:
        return None

    skill_names = [str(value).strip() for value in skills[skill_col].dropna().unique() if str(value).strip()]
    skill_spans = {name: _skill_name_matches(query, name) for name in skill_names}
    matched_skills = []
    for name, spans in skill_spans.items():
        has_uncovered_match = any(
            not any(
                len(other) > len(name)
                and other_span[0] <= span[0]
                and other_span[1] >= span[1]
                for other, other_spans in skill_spans.items()
                for other_span in other_spans
            )
            for span in spans
        )
        if has_uncovered_match:
            matched_skills.append(name)
    asks_about_skills = bool(re.search(r"\bskills?\b", query, flags=re.IGNORECASE))
    if not matched_skills and not asks_about_skills:
        return None

    selected = skills.copy()
    if matched_skills:
        selected = selected[selected[skill_col].astype(str).str.strip().str.casefold().isin(
            {name.casefold() for name in matched_skills}
        )]
    else:
        query_folded = query.casefold()
        student_ids = {
            str(student_id) for student_id in service.students.index
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(str(student_id)) + r"(?![A-Za-z0-9])", query, re.IGNORECASE)
        }
        for student_id, student in service.students.iterrows():
            name = str(student.get("student_name", "")).strip()
            if name and name.casefold() in query_folded:
                student_ids.add(str(student_id))
        if not student_ids:
            return []
        selected = selected[selected[id_col].astype(str).isin(student_ids)]

    student_lookup = service.students.copy()
    student_lookup.index = student_lookup.index.map(str)
    results = []
    for _, skill_row in selected.iterrows():
        student = student_lookup.loc[str(skill_row[id_col])] if str(skill_row[id_col]) in student_lookup.index else None
        if student is None:
            continue
        record = student.to_dict()
        record["matched_skill"] = str(skill_row[skill_col]).strip()
        record["skill_category"] = skill_row.get("Skill Category", "")
        record["skill_proficiency"] = skill_row.get("Proficiency Level (1–5)", "")
        record["skill_assessment_score"] = skill_row.get("Skill Assessment Score (%)", "")
        record["skill_evidence_source"] = skill_row.get("Evidence Source", "")
        results.append(record)
    return results


def _skill_answer(rows: list[dict], allow_detail: bool) -> str:
    if not rows:
        return "No matching student skill records were found in the loaded skills dataset. Specify a skill name recorded in the dataset to list matches."

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row["matched_skill"]), []).append(row)

    if not allow_detail:
        counts = [f"{skill}: {len({row['student_id'] for row in matches})} student(s)"
                  for skill, matches in grouped.items()]
        return (
            "Matching skill records in the dataset: " + "; ".join(counts)
            + ". Individual student names are restricted to authorized staff."
        )

    lines = []
    for skill, matches in grouped.items():
        names: dict[str, str] = {}
        for row in matches:
            student_id = str(row.get("student_id", "")).strip()
            name = str(row.get("student_name", "")).strip()
            if name and student_id:
                names[student_id] = name
        lines.append(f"{skill} ({len(names)} student(s)):")
        lines.extend(f"{number}. {name}" for number, name in enumerate(names.values(), 1))
    return "\n".join(lines)


def _aggregate_context(service: DataService) -> dict:
    df = service.students
    return {
        "dataset_scope": "Current loaded CSV datasets; computed scores and risk levels use the application's configured rules.",
        "total_students": int(len(df)),
        "average_success_score": _mean(df, "success_score"),
        "average_cgpa": _mean(df, "cgpa"),
        "average_attendance_pct": _mean(df, "overall_attendance_pct"),
        "average_assignment_completion_pct": _mean(df, "assignment_completion_pct"),
        "average_placement_readiness": _mean(df, "placement_readiness_score"),
        "academic_risk_counts": _value_counts(df, "academic_risk_level"),
        "placement_risk_counts": _value_counts(df, "placement_risk_level"),
        "placement_status_counts": _value_counts(df, "placement_status"),
        "segments": _value_counts(df, "segment"),
        "departments": _value_counts(df, "department"),
        "year_of_study_counts": _value_counts(df, "year_of_study"),
        "average_success_score_by_department": {
            str(dept): _mean(group, "success_score")
            for dept, group in df.groupby("department", dropna=False)
        },
        "average_attendance_by_department": {
            str(dept): _mean(group, "overall_attendance_pct")
            for dept, group in df.groupby("department", dropna=False)
        },
        "intervention_status_counts": _value_counts(service.interventions, "status"),
        "data_quality_note": "Missing values are unknown, not zero. Risk levels are rule-based support indicators, not probabilities or diagnoses.",
    }


def _candidate_rows(service: DataService, query: str, allow_student_detail: bool) -> list[dict]:
    if not allow_student_detail:
        return []
    df = service.students
    q = query.casefold()
    skill_rows = _skill_query_rows(service, query)
    if skill_rows is not None:
        return skill_rows[:30]

    # Explicit student ID is the strongest match.
    ids = [str(sid) for sid in df.index if str(sid).casefold() in q]
    matched = set(ids)
    # Match full student names locally; never send the names to Groq.
    names = df.get("student_name", pd.Series(dtype=str))
    for sid, name in names.items():
        name_text = str(name).strip()
        if len(name_text) >= 3 and name_text.casefold() in q:
            matched.add(str(sid))
    if matched:
        return [df.loc[sid].to_dict() for sid in sorted(matched)[:5]]

    list_question = any(phrase in q for phrase in (
        "which students", "list students", "show students", "who are", "student list",
        "compare students", "compare these", "records for", "details for", "show me students",
    ))
    if not list_question:
        # Aggregate questions need aggregate context only; do not send sample student rows unnecessarily.
        return []

    selected = df.copy()
    # Apply transparent filters inferred from the question.
    departments = [str(d) for d in df.get("department", pd.Series(dtype=str)).dropna().unique() if str(d).casefold() in q]
    if departments:
        selected = selected[selected["department"].isin(departments)]
    year_match = re.search(r"\b(?:year|yr)\s*(?:of\s*study\s*)?([1-8])\b|\b([1-8])(?:st|nd|rd|th)\s+year\b", q)
    if year_match and "year_of_study" in selected:
        year = int(year_match.group(1) or year_match.group(2))
        selected = selected[pd.to_numeric(selected["year_of_study"], errors="coerce") == year]

    academic_question = any(word in q for word in ("academic", "cgpa", "backlog", "attendance", "semester", "internal"))
    placement_question = any(word in q for word in ("placement", "job", "coding", "aptitude", "interview", "resume"))
    risk_question = any(word in q for word in ("risk", "at risk", "support", "struggling", "low performing", "needs help"))
    if risk_question and academic_question and "academic_risk_level" in selected:
        selected = selected[selected["academic_risk_level"].isin(["High", "Medium"])]
    if risk_question and placement_question and "placement_risk_level" in selected:
        selected = selected[selected["placement_risk_level"].isin(["High", "Medium"])]
    if risk_question and not academic_question and not placement_question:
        if "academic_risk_points" in selected and "placement_risk_points" in selected:
            selected = selected.assign(_risk=pd.to_numeric(selected["academic_risk_points"], errors="coerce").fillna(0) + pd.to_numeric(selected["placement_risk_points"], errors="coerce").fillna(0))
            selected = selected.sort_values("_risk", ascending=False)
    elif placement_question and "placement_readiness_score" in selected:
        selected = selected.sort_values("placement_readiness_score", ascending=True, na_position="last")
    elif academic_question and "success_score" in selected:
        selected = selected.sort_values("success_score", ascending=True, na_position="last")
    elif "success_score" in selected:
        selected = selected.sort_values("success_score", ascending=True, na_position="last")

    if not (risk_question or list_question or departments or year_match or academic_question or placement_question):
        return []
    rows = selected.head(12).to_dict("records")
    return rows


def _deidentify(rows: list[dict]) -> tuple[list[dict], dict[str, str], list[tuple[str, str]]]:
    safe_rows: list[dict] = []
    alias_to_local: dict[str, str] = {}
    replacements: list[tuple[str, str]] = []
    safe_fields = [
        "department", "year_of_study", "section", "cgpa", "backlogs", "internal_score_pct",
        "semester_score_pct", "overall_attendance_pct", "subjects_below_attendance_threshold",
        "logins_last_30_days", "assignment_completion_pct", "avg_weekly_learning_hours",
        "events_attended", "hackathons_participated", "club_participation", "volunteer_hours",
        "aptitude_score", "coding_score", "mock_interview_score", "resume_readiness_pct",
        "placement_status", "technical_skill_score", "soft_skill_score", "certifications_count",
        "projects_count", "student_satisfaction_1_to_5", "faculty_feedback_1_to_5",
        "support_requested", "feedback_topic", "success_score", "academic_risk_level",
        
        "placement_risk_points", "placement_readiness_score", "segment",
        "matched_skill", "skill_category", "skill_proficiency",
        "skill_assessment_score", "skill_evidence_source",

    ]
    for i, row in enumerate(rows, 1):
        alias = f"Learner {i}"
        sid = str(_clean_value(row.get("student_id", "")) or "")
        name = str(_clean_value(row.get("student_name", "")) or "")
        # This mapping remains local; the Groq request only contains the alias.
        alias_to_local[alias] = f"{name} ({sid})" if name and sid else (sid or name or alias)
        if sid:
            replacements.append((sid, alias))
        if name:
            replacements.append((name, alias))
        item = {key: _clean_value(row.get(key)) for key in safe_fields if key in row}
        item["record_label"] = alias
        safe_rows.append(item)
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    return safe_rows, alias_to_local, replacements


def _sanitize_question(question: str, replacements: list[tuple[str, str]], allow_detail: bool) -> str:
    safe = question
    for original, alias in replacements:
        safe = re.sub(re.escape(original), alias if allow_detail else "a student", safe, flags=re.IGNORECASE)
    return safe


def _restore_aliases(answer: str, aliases: dict[str, str]) -> str:
    # Longest aliases first to avoid partial replacement.
    for alias, local_label in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        answer = re.sub(re.escape(alias), lambda _: local_label, answer, flags=re.IGNORECASE)
    return answer


@router.post("/chat", summary="Ask Groq questions grounded in campus CSV datasets")
async def chat(body: ChatRequest, user: dict = Depends(get_current_user), service: DataService = Depends(get_service)):
    if user.get("role") not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail={"message": "Your account cannot use the AI assistant."})
    greeting = re.sub(r"[.!?,]+$", "", body.message.casefold()).strip()
    if greeting in {"hi", "hello", "hey", "hi there", "hello there", "good morning", "good afternoon", "good evening"}:
        return success({
            "answer": "Hi! Ask me about student skills, academics, attendance, placement readiness, engagement, or department trends.",
            "model": "local",
            "context_scope": "No dataset lookup required",
            "privacy": "No student records were accessed.",
        })
    if greeting in {"ok", "okay", "ok thanks", "okay thanks", "thanks", "thank you", "thanks a lot", "got it", "bye", "goodbye"}:
        return success({
            "answer": "You're welcome! Ask me whenever you need help with the campus data.",
            "model": "local",
            "context_scope": "No dataset lookup required",
            "privacy": "No student records were accessed.",
        })

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        api_key = str(dotenv_values(env_file).get("GROQ_API_KEY", "")).strip()
    if not api_key or api_key.lower().startswith(("replace_", "your_", "paste_")):
        raise HTTPException(status_code=503, detail={"message": "Groq is not configured yet. Add GROQ_API_KEY to the backend .env file and restart the API."})

    allow_detail = user.get("role") in {"admin", "faculty", "placement_officer"}
    skill_rows = _skill_query_rows(service, body.message)
    if skill_rows is not None:
        return success({
            "answer": _skill_answer(skill_rows, allow_detail),
            "model": "csv-direct",
            "context_scope": "Directly computed from student_skills.csv",
            "privacy": (
                "Individual student names are returned only to authorized staff."
                if allow_detail else "Individual records are restricted by role."
            ),
        })

    # Answer high academic-risk name queries directly from CSV data.
    # This avoids relying on Groq to calculate counts or select records.
    question = body.message.casefold()

    asks_for_high_academic_names = (
        "high" in question
        and "academic" in question
        and "risk" in question
        and any(word in question for word in (
            "name",
            "names",
            "list",
            "who",
        ))
    )

    if asks_for_high_academic_names:

        # Protect individual student information.
        if not allow_detail:
            return success({
                "answer": (
                    "Your current role can access aggregate student "
                    "analytics, but individual student names are "
                    "restricted to authorized staff."
                ),
                "model": "csv-direct",
                "context_scope": "Aggregate analytics only",
                "privacy": "Individual records are restricted by role.",
            })

        df = service.students

        # Validate that the required dataset columns exist.
        if "academic_risk_level" not in df.columns:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "The student dataset is missing the "
                        "academic_risk_level column."
                    )
                },
            )

        if "student_name" not in df.columns:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "The student dataset is missing the "
                        "student_name column."
                    )
                },
            )

        # Count only records classified as HIGH academic risk.
        risk_levels = (
            df["academic_risk_level"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        high_risk_df = df.loc[
            risk_levels.isin({
                "high",
                "high academic risk",
                "high risk",
            })
        ]

        # Retrieve actual names from the CSV, not generated names.
        names = (
            high_risk_df["student_name"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        names = names[names != ""].tolist()

        if names:
            names_text = "\n".join(
                f"{number}. {name}"
                for number, name in enumerate(names, start=1)
            )
        else:
            names_text = "No student names are recorded for these rows."

        missing_names = len(high_risk_df) - len(names)

        answer = (
            f"High Academic Risk student count: {len(high_risk_df)}\n\n"
            f"Student names ({len(names)}):\n"
            f"{names_text}"
        )

        if missing_names:
            answer += (
                f"\n\nNote: {missing_names} high-risk records "
                "do not have a recorded student name."
            )

        return success({
            "answer": answer,
            "model": "csv-direct",
            "context_scope": "Directly computed from student CSV data",
            "privacy": (
                "Individual records are returned only to authorized "
                "staff. The count is computed from academic_risk_level."
            ),
        })
    combined_query = "\n".join([*body.history[-4:], body.message])
    rows = _candidate_rows(service, combined_query, allow_detail)
    safe_rows, alias_to_local, replacements = _deidentify(rows)
    if not allow_detail:
        # Demo viewers get aggregate-only context; also scrub names/IDs from their question text.
        all_identifiers: list[tuple[str, str]] = []
        for sid, row in service.students.iterrows():
            all_identifiers.append((str(sid), "a student"))
            name = str(row.get("student_name", "")).strip()
            if len(name) >= 3:
                all_identifiers.append((name, "a student"))
        replacements = sorted(all_identifiers, key=lambda item: len(item[0]), reverse=True)
    safe_message = _sanitize_question(body.message, replacements, allow_detail)
    safe_history = [_sanitize_question(item, replacements, allow_detail) for item in body.history[-4:]]
    context = {"aggregates": _aggregate_context(service), "relevant_records": safe_rows}
    if not allow_detail:
        context["privacy_note"] = "This role is limited to aggregate analytics. Do not infer or disclose any individual student's identity or record."

    
    prompt = (
        "You are Academia AI, a student analytics assistant. "
        "Answer only from the provided dataset context. "
        "Never invent data, numbers, student names, or conclusions.\n\n"

        "STRICT RESPONSE STYLE — FOLLOW FOR EVERY QUESTION:\n"
        "- ALWAYS answer using numbered points: 1., 2., 3., etc.\n"
        "- Each point must have a short bold heading followed by a brief explanation.\n"
        "- Keep each point to a maximum of 2 short sentences.\n"
        "- Use simple, clear, direct English.\n"
        "- Include only the most relevant information for the question.\n"
        "- Avoid lengthy introductions, filler, repeated conclusions, and long paragraphs.\n"
        "- For simple questions, give 1-3 points.\n"
        "- For analytical questions, give 3-5 key findings or fewer if sufficient.\n"
        "- For recommendations, give practical actions as numbered points.\n"
        "- For comparisons, give one point per important comparison.\n"
        "- For definitions, give a brief meaning and an example when useful.\n"
        "- For missing information, state what is unavailable in one short point.\n"
        "- Use sub-bullets only when absolutely necessary.\n"
        "- Do not use tables unless explicitly requested.\n"
        "- Output normal Markdown, not escaped Markdown characters.\n"
        "- Do not write an introductory paragraph before the numbered points.\n\n"

        "DATA ACCURACY AND PRIVACY:\n"
        "- Use the supplied JSON context as the source of truth.\n"
        "- Do not estimate missing values or make unsupported comparisons.\n"
        "- Clearly distinguish dataset facts from recommendations.\n"
        "- Risk classifications are support indicators, not diagnoses or final decisions.\n"
        "- Never invent individual student records or disclose unauthorized personal data.\n\n"

        "EXAMPLE FORMAT:\n"
        "1. **Placement Readiness:** State the verified score and what it means.\n"
        "2. **Main Challenge:** State the verified pattern briefly.\n"
        "3. **Recommended Action:** Give one practical next step.\n\n"

        f"DATASET_CONTEXT_JSON:\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        f"RECENT_USER_QUESTIONS:\n"
        f"{json.dumps(safe_history, ensure_ascii=False)}\n\n"
        f"CURRENT_QUESTION:\n{safe_message}"
    )

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 700,
    }

    try:
        timeout_seconds = float(os.getenv("GROQ_TIMEOUT_SECONDS", "45"))
        timeout_seconds = max(15.0, min(timeout_seconds, 60.0))

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=10.0)
        ) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        logger.warning("Groq request timed out after %s seconds.", timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail={"message": "Groq took too long to respond. Please try again."},
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Groq network request failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=502,
            detail={"message": "Could not connect to Groq. Check your network and try again."},
        ) from exc

    if response.status_code == 401 or response.status_code == 403:
        logger.warning("Groq rejected the configured API key (HTTP %s).", response.status_code)
        raise HTTPException(status_code=502, detail={"message": "Groq rejected the configured API key. Check GROQ_API_KEY in the backend .env file."})
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail={"message": "Groq rate limit reached. Check your Groq limits or try again later."})
    if response.status_code >= 400:
        logger.warning("Groq request failed with HTTP %s.", response.status_code)
        raise HTTPException(status_code=502, detail={"message": "Groq could not complete this request. Check the configured model and API access."})
    try:
        result = response.json()
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except (ValueError, TypeError, AttributeError):
        answer = ""
    if not answer:
        raise HTTPException(status_code=502, detail={"message": "Groq returned an empty answer. Please rephrase your question and try again."})
    if allow_detail:
        answer = _restore_aliases(answer, alias_to_local)
    return success({
        "answer": answer,
        "model": model,
        "context_scope": "CSV-derived aggregates" + (" and a small set of relevant de-identified records" if safe_rows else ""),
        "privacy": "Names, student IDs and emails are removed before sending context to Groq; relevant aliases are restored locally for authorized staff.",
    })

