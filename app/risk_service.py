"""
Rule-based risk identification and student segmentation.

IMPORTANT HONESTY NOTES
  * Risk levels are RULE-BASED INDICATORS (points from simple thresholds).
    They are NOT probabilities and NOT predictions.
  * They exist to help faculty decide who to OFFER support to. They must never be
    used to automatically make adverse decisions about a student.
  * No machine learning is used here. The synthetic outcome labels are not used.

How a risk level is produced:
  1. Each rule in config.RISK_CONFIG checks one indicator (e.g. attendance < 65).
  2. A triggered rule adds its points. Missing inputs are SKIPPED (and listed in
     `missing_inputs`) instead of being counted as poor performance. If fewer than half of
     the indicators can be evaluated, the level is "Insufficient data" (never a false "Low").
  3. Total points -> level:  below medium_min = Low,  medium_min or more = Medium,  high_min or more = High
"""
from __future__ import annotations

from .config import (ALL_RISK_LEVELS, RISK_CONFIG, SEGMENT_CONFIG, SEGMENT_DESCRIPTIONS,
                     SEGMENT_INSUFFICIENT)
from .utils import is_missing

RISK_DISCLAIMER = (
    "Rule-based indicator, not a probability or a prediction. Intended only to help "
    "faculty offer support; never use it to make automatic adverse decisions."
)


def _rule_max_points(rule: dict) -> int:
    if "tiers" in rule:
        return max(t["points"] for t in rule["tiers"])
    return rule["points"]


def max_points(kind: str) -> int:
    return sum(_rule_max_points(r) for r in RISK_CONFIG[kind]["rules"])


def _evaluate_rule(rule: dict, value, context: dict) -> dict | None:
    """Return a triggered-indicator dict, or None if the rule does not trigger."""
    direction = rule["direction"]
    if direction == "equals":
        if str(value) != rule["equals"]:
            return None
        points, threshold = rule["points"], rule["equals"]
    else:
        value = float(value)
        points, threshold = None, None
        for tier in rule["tiers"]:  # strictest first
            hit = value < tier["threshold"] if direction == "below" else value >= tier["threshold"]
            if hit:
                points, threshold = tier["points"], tier["threshold"]
                break
        if points is None:
            return None
    return {
        "id": rule["id"],
        "label": rule["label"],
        "column": rule["column"],
        "value": value,
        "threshold": threshold,
        "points": points,
        "reason": rule["message"].format(value=value, threshold=threshold, **context),
        "action": rule["action"],
    }


def assess_risk(kind: str, row: dict, not_applicable_reason: str | None = None) -> dict:
    """
    Assess one student for `kind` = "academic" or "placement".
    `row` is the student's merged record (dict).
    """
    cfg = RISK_CONFIG[kind]
    levels = RISK_CONFIG["levels"]
    context = {"topic": row.get("feedback_topic") if not is_missing(row.get("feedback_topic")) else "not given"}

    triggered, missing, evaluated, points = [], [], 0, 0
    for rule in cfg["rules"]:
        value = row.get(rule["column"])
        if is_missing(value):
            missing.append(rule["column"])
            continue
        evaluated += 1
        hit = _evaluate_rule(rule, value, context)
        if hit:
            triggered.append(hit)
            points += hit["points"]

    if evaluated == 0 or evaluated / len(cfg["rules"]) < RISK_CONFIG["min_evaluated_share"]:
        level = "Insufficient data"   # too much data missing to say anything fair
    elif not_applicable_reason:
        level = "Not applicable"
    elif points >= levels["high_min_points"]:
        level = "High"
    elif points >= levels["medium_min_points"]:
        level = "Medium"
    else:
        level = "Low"

    actions: list[str] = []
    for t in triggered:
        if t["action"] not in actions:
            actions.append(t["action"])
    if level == "High":
        actions.insert(0, "Offer a supportive one-to-one conversation with a faculty or placement mentor soon")
    elif level == "Medium":
        actions.insert(0, "Check in with the student and agree on one or two small improvement goals")
    elif level == "Low":
        actions = ["No specific support indicated by these rules; continue routine monitoring"]
    elif level == "Not applicable":
        actions = [not_applicable_reason or "Not applicable"]
    else:
        actions = ["Collect the missing data before drawing any conclusion"]

    return {
        "risk_type": kind,
        "level": level,
        "points": points,
        "max_points": max_points(kind),
        "reasons": [t["reason"] for t in triggered],
        "triggered_indicators": triggered,
        "suggested_actions": actions,
        "evaluated_indicators": evaluated,
        "total_indicators": len(cfg["rules"]),
        "missing_inputs": missing,
        "note": not_applicable_reason,
        "is_probability": False,
        "disclaimer": RISK_DISCLAIMER,
    }


def assess_student(row: dict) -> dict:
    """Both assessments for one student."""
    placed = row.get("placement_status") == "Placed"
    return {
        "academic": assess_risk("academic", row),
        "placement": assess_risk(
            "placement", row,
            not_applicable_reason="Student is already marked as Placed; placement support is not needed."
            if placed else None),
    }


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------
def assign_segment(success_score, academic_level: str, placement_level: str) -> str:
    """Transparent, ordered rules (first match wins). See config.SEGMENT_CONFIG."""
    c = SEGMENT_CONFIG
    if is_missing(success_score):
        return SEGMENT_INSUFFICIENT
    score = float(success_score)
    levels = {academic_level, placement_level}
    any_high = "High" in levels
    flagged = lambda lvl: lvl in ("Medium", "High")
    both_flagged = flagged(academic_level) and flagged(placement_level)
    any_flag = flagged(academic_level) or flagged(placement_level)

    if score < c["priority_score_below"] or (any_high and score < c["priority_high_risk_score_below"]):
        return "Priority support"
    if score < c["needs_support_score_below"] or any_high or both_flagged:
        return "Needs support"
    if score >= c["high_readiness_min_score"] and not any_flag:
        return "High readiness"
    return "Developing"


def segment_descriptions() -> dict:
    return {name: text.format(**SEGMENT_CONFIG) for name, text in SEGMENT_DESCRIPTIONS.items()}


def valid_risk_levels() -> list[str]:
    return list(ALL_RISK_LEVELS)
