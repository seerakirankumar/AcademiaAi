"""Risk rules, segmentation and recommendations."""
import math

import pytest

from app.recommendation_service import build_recommendations
from app.risk_service import assess_risk, assess_student, assign_segment


def student(**kw):
    base = dict(cgpa=8.0, semester_score_pct=75.0, internal_score_pct=75.0, backlogs=0,
                overall_attendance_pct=90.0, subjects_below_attendance_threshold=0,
                assignment_completion_pct=85.0, support_requested="No", feedback_topic="No concern",
                aptitude_score=70.0, coding_score=70.0, mock_interview_score=70.0,
                resume_readiness_pct=70.0, technical_skill_score=70.0, soft_skill_score=70.0,
                projects_count=2, placement_status="Eligible")
    base.update(kw)
    return base


def test_healthy_student_is_low_risk():
    a = assess_risk("academic", student())
    assert a["level"] == "Low" and a["points"] == 0 and a["reasons"] == []


def test_struggling_student_is_high_risk_with_reasons_and_actions():
    a = assess_risk("academic", student(cgpa=5.0, backlogs=4, overall_attendance_pct=55.0,
                                        assignment_completion_pct=40.0))
    assert a["level"] == "High"
    text = " ".join(a["reasons"])
    assert "CGPA is 5.00" in text and "4 backlog" in text and "55.0%" in text and "40.0%" in text
    assert len(a["suggested_actions"]) >= 3


def test_risk_is_never_a_probability():
    for kind in ("academic", "placement"):
        r = assess_risk(kind, student(cgpa=3.0))
        assert r["is_probability"] is False and "not a probability" in r["disclaimer"]


def test_missing_inputs_are_skipped_not_penalised():
    a = assess_risk("academic", student(cgpa=float("nan"), backlogs=None))
    assert a["points"] == 0 and a["level"] == "Low"
    assert set(a["missing_inputs"]) == {"cgpa", "backlogs"}
    assert a["evaluated_indicators"] == a["total_indicators"] - 2


def test_all_inputs_missing_gives_insufficient_data():
    empty = {k: math.nan for k in student()}
    assert assess_risk("placement", empty)["level"] == "Insufficient data"


def test_placed_students_have_no_placement_risk_level():
    r = assess_student(student(placement_status="Placed", aptitude_score=10.0))
    assert r["placement"]["level"] == "Not applicable"
    assert r["academic"]["level"] == "Low"


def test_support_request_adds_a_point_and_uses_the_topic():
    r = assess_risk("placement", student(support_requested="Yes", feedback_topic="Career guidance"))
    assert r["points"] == 1 and "Career guidance" in r["reasons"][0]


@pytest.mark.parametrize("score,acad,plac,expected", [
    (80, "Low", "Low", "High readiness"),
    (80, "Medium", "Low", "Developing"),
    (65, "Low", "Low", "Developing"),
    (65, "High", "Low", "Needs support"),
    (65, "Medium", "Medium", "Needs support"),
    (50, "Low", "Low", "Needs support"),
    (50, "High", "Low", "Priority support"),
    (40, "Low", "Low", "Priority support"),
    (None, "Low", "Low", "Insufficient data"),
])
def test_segment_rules(score, acad, plac, expected):
    assert assign_segment(score, acad, plac) == expected


def test_recommendations_are_linked_to_the_students_actual_indicators():
    row = student(overall_attendance_pct=60.0, subjects_below_attendance_threshold=2, coding_score=30.0,
                  backlogs=2, success_score=50.0)
    recs = {r["id"]: r for r in build_recommendations(row, [])}
    assert {"attendance_support", "coding_practice", "backlog_preparation"} <= set(recs)
    assert recs["attendance_support"]["priority"] == "High"
    assert {b["indicator"] for b in recs["attendance_support"]["based_on"]} == {
        "overall_attendance_pct", "subjects_below_attendance_threshold"}
    assert "aptitude" not in " ".join(recs)          # healthy aptitude -> no aptitude recommendation


def test_healthy_student_gets_only_a_growth_suggestion():
    recs = build_recommendations(student(success_score=85.0), [])
    assert [r["id"] for r in recs] == ["maintain_momentum"]


def test_recommendation_notes_existing_open_intervention():
    open_iv = [{"intervention_id": "INT0042", "intervention_type": "Coding practice", "status": "In progress"}]
    recs = build_recommendations(student(coding_score=20.0), open_iv)
    coding = next(r for r in recs if r["id"] == "coding_practice")
    assert coding["existing_open_intervention"] == {"intervention_id": "INT0042", "status": "In progress"}


def test_academic_recommendation_admits_there_is_no_subject_level_data():
    recs = build_recommendations(student(cgpa=5.0), [])
    rev = next(r for r in recs if r["id"] == "academic_revision")
    assert "subject-wise" in rev["description"]


def test_mostly_missing_data_is_insufficient_not_a_false_low():
    # 6 of the 8 placement indicators missing -> must NOT be reported as "Low"
    row = student(aptitude_score=None, coding_score=None, mock_interview_score=None,
                  resume_readiness_pct=None, technical_skill_score=None, soft_skill_score=None)
    r = assess_risk("placement", row)
    assert r["level"] == "Insufficient data"
    assert r["evaluated_indicators"] == 2
