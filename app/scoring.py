"""
Student Success Score (0-100).

HOW IT WORKS (each step is a plain formula you can explain in an interview):

1. Every raw input is converted to a 0-100 "sub-score".
2. Sub-scores are combined into 4 component scores using a weighted average.
3. The 4 components are combined into the Student Success Score using the
   overall weights (Academic 40%, Attendance 20%, LMS 15%, Placement 25%).

MISSING DATA: a missing value is NEVER treated as zero. If an input is missing,
the remaining inputs of that component are re-weighted. If too much is missing
(see `min_component_coverage` / `min_overall_coverage` in config.py) the score is
left empty (null) and `coverage` tells the caller how much data was available.

All weights/targets come from config.SCORE_CONFIG, so faculty can adjust them.
This is a PROTOTYPE score, not an official institutional measurement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import COMPONENT_LABELS, SCORE_CONFIG
from .utils import is_missing

COMPONENTS = ["academic", "attendance", "lms", "placement_readiness"]


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Numeric column, or an all-NaN series if the column is absent."""
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def weighted_mean(parts: dict[str, pd.Series], weights: dict[str, float],
                  min_coverage: float) -> tuple[pd.Series, pd.Series]:
    """
    Weighted average that ignores missing parts (re-weighting what is left).

    Returns (score, coverage):
      coverage = share of the total weight that had data (0..1)
      score    = NaN when coverage < min_coverage
    """
    frame = pd.DataFrame(parts)
    w = pd.Series({k: weights[k] for k in frame.columns})
    available = frame.notna()
    weight_available = (available * w).sum(axis=1)
    numerator = (frame.fillna(0.0) * w).sum(axis=1)
    score = numerator / weight_available.where(weight_available > 0)
    coverage = weight_available / w.sum()
    score = score.where(coverage >= min_coverage)
    return score, coverage


def compute_subscores(df: pd.DataFrame, cfg: dict = SCORE_CONFIG) -> dict[str, dict[str, pd.Series]]:
    """Step 1: raw inputs -> 0-100 sub-scores, grouped by component."""
    ac, at, lm = cfg["academic"], cfg["attendance"], cfg["lms"]

    academic = {
        "cgpa": _col(df, "cgpa") / ac["cgpa_scale_max"] * 100,
        "semester_score": _col(df, "semester_score_pct"),
        "internal_score": _col(df, "internal_score_pct"),
        "backlogs": 100 - _col(df, "backlogs") * ac["backlog_penalty_per_backlog"],
    }
    # Attendance: overall % minus a penalty for each subject below the threshold.
    # (If the subject count is missing, no penalty is applied.)
    attendance = {
        "attendance": _col(df, "overall_attendance_pct")
        - _col(df, "subjects_below_attendance_threshold").fillna(0) * at["penalty_per_subject_below_threshold"],
    }
    lms = {
        "assignment_completion": _col(df, "assignment_completion_pct"),
        "logins": _col(df, "logins_last_30_days") / lm["target_logins_30_days"] * 100,
        "learning_hours": _col(df, "avg_weekly_learning_hours") / lm["target_weekly_learning_hours"] * 100,
    }
    placement = {
        "aptitude": _col(df, "aptitude_score"),
        "coding": _col(df, "coding_score"),
        "mock_interview": _col(df, "mock_interview_score"),
        "resume": _col(df, "resume_readiness_pct"),
        "technical_skills": _col(df, "technical_skill_score"),
        "soft_skills": _col(df, "soft_skill_score"),
    }
    groups = {"academic": academic, "attendance": attendance, "lms": lms,
              "placement_readiness": placement}
    # Keep every sub-score inside 0-100 (e.g. 25 logins would otherwise give 125).
    return {comp: {k: v.clip(0, 100) for k, v in subs.items()} for comp, subs in groups.items()}


def compute_scores(df: pd.DataFrame, cfg: dict = SCORE_CONFIG) -> pd.DataFrame:
    """
    Steps 1-3 for every student at once.

    Output columns (same index as `df`):
      sub__<component>__<name>  - each 0-100 sub-score (used for explanations)
      <component>_score         - component scores (0-100 or NaN)
      <component>_coverage      - share of that component's inputs that were available
      success_score             - overall score (0-100 or NaN), rounded to 2 decimals
      success_coverage          - share of the overall weight that was available
    """
    subs = compute_subscores(df, cfg)
    out = pd.DataFrame(index=df.index)
    comp_scores: dict[str, pd.Series] = {}

    for comp in COMPONENTS:
        for name, series in subs[comp].items():
            out[f"sub__{comp}__{name}"] = series
        score, coverage = weighted_mean(subs[comp], cfg[comp]["weights"], cfg["min_component_coverage"])
        comp_scores[comp] = score
        out[f"{comp}_score"] = score.clip(0, 100).round(2)
        out[f"{comp}_coverage"] = coverage.round(3)

    overall, coverage = weighted_mean(comp_scores, cfg["overall_weights"], cfg["min_overall_coverage"])
    out["success_score"] = overall.clip(0, 100).round(2)
    out["success_coverage"] = coverage.round(3)
    return out


# --------------------------------------------------------------------------
# Human-readable formulas and per-student explanation
# --------------------------------------------------------------------------
def describe_formulas(cfg: dict = SCORE_CONFIG) -> dict:
    """The score formulas in plain language, generated from the live configuration."""
    ac, at, lm = cfg["academic"], cfg["attendance"], cfg["lms"]
    return {
        "overall": "success_score = sum(component_score x weight) / sum(weights of available components)",
        "components": {
            "academic": {
                "cgpa": f"cgpa / {ac['cgpa_scale_max']:g} x 100  (CGPA scale assumed 0-{ac['cgpa_scale_max']:g})",
                "semester_score": "semester_score_pct (already 0-100)",
                "internal_score": "internal_score_pct (already 0-100)",
                "backlogs": f"100 - backlogs x {ac['backlog_penalty_per_backlog']:g}  (minimum 0)",
            },
            "attendance": {
                "attendance": f"overall_attendance_pct - subjects_below_attendance_threshold x "
                              f"{at['penalty_per_subject_below_threshold']:g}  (clipped to 0-100)",
            },
            "lms": {
                "assignment_completion": "assignment_completion_pct (already 0-100)",
                "logins": f"logins_last_30_days / {lm['target_logins_30_days']} x 100  (capped at 100)",
                "learning_hours": f"avg_weekly_learning_hours / {lm['target_weekly_learning_hours']} x 100  (capped at 100)",
            },
            "placement_readiness": {
                "aptitude": "aptitude_score (0-100)",
                "coding": "coding_score (0-100)",
                "mock_interview": "mock_interview_score (0-100)",
                "resume": "resume_readiness_pct (0-100)",
                "technical_skills": "technical_skill_score (0-100)",
                "soft_skills": "soft_skill_score (0-100)",
            },
        },
        "missing_data_rule": (
            f"Missing inputs are never counted as zero. Remaining inputs are re-weighted; a component "
            f"needs at least {cfg['min_component_coverage']:.0%} of its input weight and the overall "
            f"score at least {cfg['min_overall_coverage']:.0%} of the total weight, otherwise it is null."
        ),
    }


_RAW_COLUMNS = {
    "academic": {"cgpa": ["cgpa"], "semester_score": ["semester_score_pct"],
                 "internal_score": ["internal_score_pct"], "backlogs": ["backlogs"]},
    "attendance": {"attendance": ["overall_attendance_pct", "subjects_below_attendance_threshold"]},
    "lms": {"assignment_completion": ["assignment_completion_pct"], "logins": ["logins_last_30_days"],
            "learning_hours": ["avg_weekly_learning_hours"]},
    "placement_readiness": {"aptitude": ["aptitude_score"], "coding": ["coding_score"],
                            "mock_interview": ["mock_interview_score"], "resume": ["resume_readiness_pct"],
                            "technical_skills": ["technical_skill_score"], "soft_skills": ["soft_skill_score"]},
}


def _num(row, key):
    v = row.get(key)
    return None if is_missing(v) else float(v)


def explain_score(row: dict, cfg: dict = SCORE_CONFIG) -> dict:
    """
    Per-student breakdown: for each component, the inputs, normalised sub-scores,
    weights and how many points it contributes to the final score.
    """
    formulas = describe_formulas(cfg)["components"]
    overall_w = cfg["overall_weights"]
    available_w = sum(w for c, w in overall_w.items() if _num(row, f"{c}_score") is not None)

    components = {}
    for comp in COMPONENTS:
        score = _num(row, f"{comp}_score")
        eff = (overall_w[comp] / available_w) if (score is not None and available_w > 0) else 0.0
        inputs = []
        for sub, weight in cfg[comp]["weights"].items():
            inputs.append({
                "name": sub,
                "raw_values": {c: (None if is_missing(row.get(c)) else row.get(c))
                               for c in _RAW_COLUMNS[comp][sub]},
                "normalized_score": None if _num(row, f"sub__{comp}__{sub}") is None
                else round(_num(row, f"sub__{comp}__{sub}"), 2),
                "weight_within_component": weight,
                "formula": formulas[comp][sub],
            })
        components[comp] = {
            "label": COMPONENT_LABELS[comp],
            "score": score,
            "weight": overall_w[comp],
            "effective_weight": round(eff, 4),
            "points_contributed": None if score is None else round(score * eff, 2),
            "input_coverage": _num(row, f"{comp}_coverage"),
            "inputs": inputs,
        }
    return {
        "success_score": _num(row, "success_score"),
        "score_coverage": _num(row, "success_coverage"),
        "components": components,
    }
