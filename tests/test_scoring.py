"""Score calculation tests, using tiny hand-made tables whose answers can be checked by hand."""
import numpy as np
import pandas as pd
import pytest

from app.config import SCORE_CONFIG
from app.scoring import compute_scores, explain_score, weighted_mean


def make_df(**overrides):
    base = dict(cgpa=8.0, backlogs=0, internal_score_pct=80.0, semester_score_pct=70.0,
                overall_attendance_pct=90.0, subjects_below_attendance_threshold=0,
                assignment_completion_pct=80.0, logins_last_30_days=20, avg_weekly_learning_hours=6.0,
                aptitude_score=60.0, coding_score=60.0, mock_interview_score=60.0,
                resume_readiness_pct=60.0, technical_skill_score=60.0, soft_skill_score=60.0)
    base.update(overrides)
    return pd.DataFrame([base])


def test_overall_weights_sum_to_one_and_match_the_brief():
    w = SCORE_CONFIG["overall_weights"]
    assert w == {"academic": 0.40, "attendance": 0.20, "lms": 0.15, "placement_readiness": 0.25}
    assert sum(w.values()) == pytest.approx(1.0)
    for comp in ("academic", "attendance", "lms", "placement_readiness"):
        assert sum(SCORE_CONFIG[comp]["weights"].values()) == pytest.approx(1.0)


def test_academic_component_by_hand():
    # .40*80 (cgpa 8/10) + .25*70 + .20*80 + .15*100 (no backlogs) = 80.5
    out = compute_scores(make_df())
    assert out.loc[0, "academic_score"] == pytest.approx(80.5)


def test_backlogs_reduce_academic_score_and_floor_at_zero():
    one = compute_scores(make_df(backlogs=1)).loc[0, "academic_score"]
    many = compute_scores(make_df(backlogs=9)).loc[0, "academic_score"]
    assert one == pytest.approx(80.5 - 0.15 * 20)       # one backlog = -20 sub-score points
    assert many == pytest.approx(80.5 - 0.15 * 100)     # sub-score floors at 0, never negative


def test_attendance_penalty_and_clipping():
    assert compute_scores(make_df(subjects_below_attendance_threshold=2)).loc[0, "attendance_score"] == pytest.approx(80.0)
    assert compute_scores(make_df(overall_attendance_pct=3.0, subjects_below_attendance_threshold=5)).loc[0, "attendance_score"] == 0.0


def test_lms_component_by_hand_and_caps():
    # .5*80 + .25*100 + .25*100 = 90 (20 logins and 6 h are exactly the targets)
    assert compute_scores(make_df()).loc[0, "lms_score"] == pytest.approx(90.0)
    capped = compute_scores(make_df(logins_last_30_days=500, avg_weekly_learning_hours=90.0))
    assert capped.loc[0, "lms_score"] == pytest.approx(0.5 * 80 + 25 + 25)   # capped at 100 each


def test_placement_readiness_by_hand():
    out = compute_scores(make_df(aptitude_score=100, coding_score=0))
    expected = .20 * 100 + .20 * 0 + .15 * 60 + .15 * 60 + .20 * 60 + .10 * 60
    assert out.loc[0, "placement_readiness_score"] == pytest.approx(expected)


def test_overall_score_by_hand():
    out = compute_scores(make_df())
    expected = .40 * 80.5 + .20 * 90 + .15 * 90 + .25 * 60
    assert out.loc[0, "success_score"] == pytest.approx(expected, abs=0.01)


def test_scores_always_between_0_and_100():
    extreme = pd.concat([make_df(cgpa=10, internal_score_pct=100, semester_score_pct=100,
                                 overall_attendance_pct=100, assignment_completion_pct=100,
                                 aptitude_score=100, coding_score=100, mock_interview_score=100,
                                 resume_readiness_pct=100, technical_skill_score=100, soft_skill_score=100),
                         make_df(cgpa=0, backlogs=50, internal_score_pct=0, semester_score_pct=0,
                                 overall_attendance_pct=0, assignment_completion_pct=0, logins_last_30_days=0,
                                 avg_weekly_learning_hours=0, aptitude_score=0, coding_score=0,
                                 mock_interview_score=0, resume_readiness_pct=0, technical_skill_score=0,
                                 soft_skill_score=0)], ignore_index=True)
    out = compute_scores(extreme)
    assert out.loc[0, "success_score"] == pytest.approx(100.0)
    assert out.loc[1, "success_score"] == 0.0
    score_cols = [c for c in out.columns if c.endswith("_score")]
    assert ((out[score_cols] >= 0) & (out[score_cols] <= 100)).all().all()


def test_missing_input_is_reweighted_not_treated_as_zero():
    full = compute_scores(make_df()).loc[0, "academic_score"]
    # Remove the semester score: the other three inputs are re-weighted, NOT counted as 0.
    partial = compute_scores(make_df(semester_score_pct=np.nan))
    expected = (.40 * 80 + .20 * 80 + .15 * 100) / (.40 + .20 + .15)
    assert partial.loc[0, "academic_score"] == pytest.approx(expected)
    assert partial.loc[0, "academic_score"] != pytest.approx(.40 * 80 + .20 * 80 + .15 * 100)  # the "zero" answer
    assert partial.loc[0, "academic_coverage"] == pytest.approx(0.75)
    assert full == pytest.approx(80.5)


def test_too_much_missing_data_gives_null_score_not_zero():
    out = compute_scores(make_df(cgpa=np.nan, semester_score_pct=np.nan, internal_score_pct=np.nan))
    assert np.isnan(out.loc[0, "academic_score"])            # only backlogs (15%) left: below 50% coverage


def test_overall_score_reweights_when_a_component_is_missing():
    df = make_df(aptitude_score=np.nan, coding_score=np.nan, mock_interview_score=np.nan,
                 resume_readiness_pct=np.nan, technical_skill_score=np.nan, soft_skill_score=np.nan)
    out = compute_scores(df)
    assert np.isnan(out.loc[0, "placement_readiness_score"])
    expected = (.40 * 80.5 + .20 * 90 + .15 * 90) / .75
    assert out.loc[0, "success_score"] == pytest.approx(expected, abs=0.01)
    assert out.loc[0, "success_coverage"] == pytest.approx(0.75)


def test_weighted_mean_helper():
    parts = {"a": pd.Series([10.0, np.nan]), "b": pd.Series([20.0, 40.0])}
    score, coverage = weighted_mean(parts, {"a": 0.5, "b": 0.5}, min_coverage=0.5)
    assert score.tolist() == [15.0, 40.0]
    assert coverage.tolist() == [1.0, 0.5]


def test_explanation_contributions_add_up_to_the_score():
    df = make_df()
    row = pd.concat([df, compute_scores(df)], axis=1).iloc[0].to_dict()
    ex = explain_score(row)
    total = sum(c["points_contributed"] for c in ex["components"].values())
    assert total == pytest.approx(ex["success_score"], abs=0.05)
    assert {"formula"} <= set(ex["components"]["academic"]["inputs"][0])
