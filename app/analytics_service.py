"""Aggregations for the React dashboard. Every number is calculated from the loaded CSV data."""
from __future__ import annotations

import re

import pandas as pd

from .config import (ALL_RISK_LEVELS, DATASET_FILES, DATASET_SCHEMAS, FEATURE_DATASETS,
                     INTERVENTION_STATUSES, INTERVENTION_TYPES, RISK_LEVELS, SCORE_CONFIG,
                     SEGMENT_CONFIG, SEGMENT_INSUFFICIENT, SEGMENTS, STRONG_PLACEMENT_READINESS_MIN,
                     SUPPORT_LEVELS)
from .data_service import DataService
from .risk_service import segment_descriptions
from .utils import round_or_none

ALL_SEGMENTS = SEGMENTS + [SEGMENT_INSUFFICIENT]


def _mean(series: pd.Series, digits: int = 2):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return round_or_none(s.mean(), digits) if len(s) else None


def _flag_counts(df: pd.DataFrame) -> dict:
    return {
        "academic_support": int(df["academic_risk_level"].isin(SUPPORT_LEVELS).sum()),
        "placement_support": int(df["placement_risk_level"].isin(SUPPORT_LEVELS).sum()),
        "high_risk_academic": int((df["academic_risk_level"] == "High").sum()),
        "high_risk_placement": int((df["placement_risk_level"] == "High").sum()),
        "priority_support": int((df["segment"] == "Priority support").sum()),
        "strong_placement_readiness": int((df["placement_readiness_score"] >= STRONG_PLACEMENT_READINESS_MIN).sum()),
    }


def segment_counts(df: pd.DataFrame) -> dict:
    counts = df["segment"].value_counts().to_dict()
    return {s: int(counts.get(s, 0)) for s in ALL_SEGMENTS if counts.get(s, 0) or s in SEGMENTS}


def dashboard_summary(service: DataService) -> dict:
    df = service.students
    total = int(len(df))
    flags = _flag_counts(df)
    open_iv = service.interventions["status"].isin(["Recommended", "Assigned", "In progress"]).sum()
    return {
        "total_students": total,
        "average_success_score": _mean(df["success_score"]),
        "average_attendance_pct": _mean(df["overall_attendance_pct"]),
        "students_flagged_academic_support": flags["academic_support"],
        "students_flagged_placement_support": flags["placement_support"],
        "students_high_priority_support": flags["priority_support"],
        "students_strong_placement_readiness": flags["strong_placement_readiness"],
        "high_risk_academic": flags["high_risk_academic"],
        "high_risk_placement": flags["high_risk_placement"],
        "students_with_incomplete_data": int((df["data_completeness_pct"] < 100).sum()),
        "segments": segment_counts(df),
        "placement_status_counts": {k: int(v) for k, v in df["placement_status"].value_counts().items()},
        "open_interventions": int(open_iv),
        "total_interventions": int(len(service.interventions)),
        "definitions": {
            "flagged_support": f"Risk level in {SUPPORT_LEVELS} (rule-based indicator, not a probability)",
            "high_priority_support": "Segment 'Priority support': " + segment_descriptions()["Priority support"],
            "strong_placement_readiness": f"Placement readiness score >= {STRONG_PLACEMENT_READINESS_MIN}",
            "placed_students": "Students with placement_status = 'Placed' have placement risk 'Not applicable' "
                               "and are not counted as needing placement support.",
        },
        "disclaimer": "Prototype indicators from preliminary rules; synthetic demo data.",
    }


def department_metrics(service: DataService) -> list[dict]:
    df = service.students
    rows = []
    for dept, g in df.groupby("department", sort=True):
        flags = _flag_counts(g)
        rows.append({
            "department": dept,
            "students": int(len(g)),
            "average_success_score": _mean(g["success_score"]),
            "average_cgpa": _mean(g["cgpa"]),
            "average_attendance_pct": _mean(g["overall_attendance_pct"]),
            "average_lms_score": _mean(g["lms_score"]),
            "average_placement_readiness": _mean(g["placement_readiness_score"]),
            "flagged_academic_support": flags["academic_support"],
            "flagged_placement_support": flags["placement_support"],
            "priority_support": flags["priority_support"],
            "strong_placement_readiness": flags["strong_placement_readiness"],
            "placed_students": int((g["placement_status"] == "Placed").sum()),
            "segments": segment_counts(g),
        })
    return rows


def segment_summaries(service: DataService) -> list[dict]:
    df = service.students
    total = len(df)
    descriptions = segment_descriptions()
    out = []
    for seg in ALL_SEGMENTS:
        g = df[df["segment"] == seg]
        if g.empty and seg == SEGMENT_INSUFFICIENT:
            continue
        out.append({
            "segment": seg,
            "description": descriptions.get(seg),
            "students": int(len(g)),
            "percentage": round(len(g) / total * 100, 1) if total else 0.0,
            "average_success_score": _mean(g["success_score"]),
            "average_attendance_pct": _mean(g["overall_attendance_pct"]),
            "average_placement_readiness": _mean(g["placement_readiness_score"]),
            "by_department": {k: int(v) for k, v in g["department"].value_counts().sort_index().items()},
        })
    return out


# A column counts as a date only if its NAME contains a whole date-word ("assigned_date",
# "record_month") or its VALUES parse as ISO dates. Substring matching was rejected on purpose:
# "avg_weekly_learning_hours" and "logins_last_30_days" are measurements, not dates.
_DATE_WORDS = {"date", "datetime", "timestamp", "month", "week", "day", "period", "semester_start"}


def _date_like_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    found = []
    for col in columns:
        if col not in df.columns:
            continue
        name_hit = bool(_DATE_WORDS & set(re.split(r"[_\W]+", col.lower())))
        series = df[col].dropna()
        value_hit = False
        if len(series) and not pd.api.types.is_numeric_dtype(series):
            parsed = pd.to_datetime(series.astype(str), errors="coerce", format="%Y-%m-%d")
            value_hit = bool(parsed.notna().mean() > 0.8)
        if name_hit or value_hit:
            found.append(col)
    return found


def trends(service: DataService) -> dict:
    """
    Honest trend check: look for historical dates / repeated measurements per student.
    Nothing is generated or estimated; if history does not exist we say so.
    """
    checked, has_history = [], False
    df = service.students
    for name in FEATURE_DATASETS + ["students"]:
        cols = DATASET_SCHEMAS[name]["required"]
        date_cols = _date_like_columns(df, [c for c in cols if c != "student_id"])
        checked.append({
            "dataset": name, "file": DATASET_FILES[name],
            "date_like_columns": date_cols,
            "max_rows_per_student": 1,   # validated at load time: duplicate student_id values are rejected
        })
        has_history = has_history or bool(date_cols)

    iv = service.interventions
    weekly = []
    if not iv.empty and iv["assigned_date"].notna().any():
        dates = pd.to_datetime(iv["assigned_date"], errors="coerce").dropna()
        by_week = dates.dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d").value_counts().sort_index()
        weekly = [{"week_starting": k, "interventions_assigned": int(v)} for k, v in by_week.items()]

    return {
        "available": bool(has_history),
        "reason": None if has_history else (
            "Trend analysis is unavailable: every student dataset holds a single snapshot per student "
            "(one row per student_id, no dates or repeated measurements), so changes over time cannot "
            "be calculated. No trend values have been generated."),
        "datasets_checked": checked,
        "student_trends": [],
        "intervention_activity": {
            "note": "Only the intervention log has dates. This shows how many interventions were "
                    "assigned per week; it says NOTHING about student performance trends.",
            "date_range": {"first": iv["assigned_date"].min() if not iv.empty else None,
                           "last": iv["assigned_date"].max() if not iv.empty else None},
            "weekly_counts": weekly,
        },
        "how_to_enable": "Provide repeated measurements (e.g. attendance or scores per month/semester "
                         "with a date column) and extend this endpoint.",
    }


def metadata(service: DataService) -> dict:
    df = service.students
    return {
        "departments": service.departments(),
        "years_of_study": sorted(int(y) for y in df["year_of_study"].dropna().unique()),
        "admission_years": sorted(int(y) for y in df["admission_year"].dropna().unique()),
        "sections": sorted(df["section"].dropna().unique().tolist()),
        "placement_statuses": sorted(df["placement_status"].dropna().unique().tolist()),
        "risk_levels": RISK_LEVELS,
        "all_risk_level_values": ALL_RISK_LEVELS,
        "segments": SEGMENTS,
        "intervention_types": INTERVENTION_TYPES,
        "intervention_statuses": INTERVENTION_STATUSES,
        "score_weights": SCORE_CONFIG["overall_weights"],
        "segment_rules": SEGMENT_CONFIG,
        "datasets": service.dataset_info,
        "data_notes": [
            "Dataset imported from the supplied workbook and transformed into working CSV tables.",
            "Scores and support indicators use preliminary rule-based assumptions; they are not probabilities.",
            "CSV files in the data folder are the source of truth; admin changes are written to these files.",
        ],
        "warnings": service.warnings,
    }
