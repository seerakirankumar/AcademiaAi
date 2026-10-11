"""Builds the JSON structures returned for a single student."""
from __future__ import annotations

from .config import SCORE_CONFIG
from .data_service import DataService
from .recommendation_service import build_recommendations
from .risk_service import RISK_DISCLAIMER, segment_descriptions
from .scoring import describe_formulas, explain_score
from .utils import is_missing

SCORE_NOTE = (
    "Prototype score from preliminary weights; it needs faculty validation and is not an "
    "official institutional measurement."
)


def _pick(row: dict, columns: list[str]) -> dict:
    return {c: (None if is_missing(row.get(c)) else row.get(c)) for c in columns}


def list_item(row: dict) -> dict:
    """Compact row used in student lists."""
    return {
        **_pick(row, ["student_id", "student_name", "department", "year_of_study", "section",
                      "cgpa", "overall_attendance_pct", "placement_status", "success_score",
                      "academic_risk_level", "placement_risk_level", "segment"]),
    }


def risk_item(row: dict, risk: dict) -> dict:
    return {
        **_pick(row, ["student_id", "student_name", "department", "year_of_study", "section",
                      "success_score", "segment"]),
        "academic_risk": _risk_view(risk["academic"]),
        "placement_risk": _risk_view(risk["placement"]),
    }


def _risk_view(r: dict) -> dict:
    return {k: r[k] for k in ("level", "points", "max_points", "reasons", "suggested_actions",
                              "missing_inputs", "note", "is_probability")}


def score_breakdown(service: DataService, student_id: str) -> dict:
    row = service.student_row(student_id)
    formulas = describe_formulas(SCORE_CONFIG)
    return {
        "student_id": row["student_id"],
        "student_name": row["student_name"],
        **explain_score(row),
        "formula": formulas,
        "assumptions": {
            "overall_weights": SCORE_CONFIG["overall_weights"],
            "cgpa_scale_max": SCORE_CONFIG["academic"]["cgpa_scale_max"],
            "lms_targets": {"logins_30_days": SCORE_CONFIG["lms"]["target_logins_30_days"],
                            "weekly_learning_hours": SCORE_CONFIG["lms"]["target_weekly_learning_hours"]},
            "configured_in": "app/config.py (SCORE_CONFIG)",
        },
        "note": SCORE_NOTE,
        "is_official_measure": False,
    }


def recommendations_for(service: DataService, student_id: str) -> dict:
    row = service.student_row(student_id)
    recs = build_recommendations(row, service.open_interventions_for(row["student_id"]))
    return {
        "student_id": row["student_id"],
        "student_name": row["student_name"],
        "recommendations": recs,
        "count": len(recs),
        "note": ("Supportive suggestions generated from the student's recorded indicators. "
                 "They are for discussion with a mentor, not automatic decisions."),
        "data_limitations": ["No subject-wise marks are available, so revision plans cannot name subjects."],
    }


def build_profile(service: DataService, student_id: str) -> dict:
    row = service.student_row(student_id)
    sid = row["student_id"]
    risk = service.risk_details[sid]
    open_iv = service.open_interventions_for(sid)
    missing_fields = [c for c in service.feature_columns if is_missing(row.get(c))]
    seg = row["segment"]
    return {
        "student_id": sid,
        "personal": _pick(row, ["student_name", "department", "year_of_study", "section",
                                "admission_year", "student_email"]),
        "academics": {**_pick(row, ["cgpa", "backlogs", "internal_score_pct", "semester_score_pct"]),
                      "cgpa_scale_max": SCORE_CONFIG["academic"]["cgpa_scale_max"]},
        "attendance": _pick(row, ["overall_attendance_pct", "subjects_below_attendance_threshold"]),
        "lms": _pick(row, ["logins_last_30_days", "assignment_completion_pct", "avg_weekly_learning_hours"]),
        "engagement": _pick(row, ["events_attended", "hackathons_participated", "club_participation",
                                  "volunteer_hours"]),
        "feedback": _pick(row, ["student_satisfaction_1_to_5", "faculty_feedback_1_to_5",
                                "support_requested", "feedback_topic"]),
        "skills": _pick(row, ["technical_skill_score", "soft_skill_score", "certifications_count",
                              "projects_count"]),
        "placement": _pick(row, ["aptitude_score", "coding_score", "mock_interview_score",
                                 "resume_readiness_pct", "placement_status"]),
        "success_score": {
            "score": None if is_missing(row["success_score"]) else row["success_score"],
            "coverage": row["success_coverage"],
            "components": {c: {"score": None if is_missing(row[f"{c}_score"]) else row[f"{c}_score"],
                               "weight": w}
                           for c, w in SCORE_CONFIG["overall_weights"].items()},
            "details_endpoint": f"/api/students/{sid}/score",
            "note": SCORE_NOTE,
        },
        "segment": {"name": seg, "description": segment_descriptions().get(seg)},
        "risk": {
            "academic": {k: v for k, v in risk["academic"].items() if k != "triggered_indicators"},
            "placement": {k: v for k, v in risk["placement"].items() if k != "triggered_indicators"},
            "disclaimer": RISK_DISCLAIMER,
        },
        "recommendations": build_recommendations(row, open_iv),
        "interventions": service.student_interventions(sid),
        "data_quality": {
            "completeness_pct": row["data_completeness_pct"],
            "missing_fields": missing_fields,
        },
    }
