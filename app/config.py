"""
Central configuration for Smart Campus Analytics.

Everything a faculty member might want to tune (weights, thresholds, risk
rules) lives in this one file, so the logic files (scoring.py, risk_service.py,
...) contain no magic numbers.

IMPORTANT: every weight and threshold below is a PRELIMINARY ASSUMPTION made for
this prototype. None of them is an official institutional measurement. They must
be reviewed and validated by faculty before being used for any real decision.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def get_data_dir(override: str | Path | None = None) -> Path:
    """Data folder: explicit argument > SMART_CAMPUS_DATA_DIR env var > ./data"""
    if override:
        return Path(override)
    env = os.environ.get("SMART_CAMPUS_DATA_DIR")
    return Path(env) if env else DEFAULT_DATA_DIR


# --------------------------------------------------------------------------
# Dataset files (the REAL file names supplied with the project)
# --------------------------------------------------------------------------
DATASET_FILES = {
    "students": "students.csv",
    "academics": "academics.csv",
    "attendance": "attendance.csv",
    "lms": "lms.csv",
    "engagement": "engagement.csv",
    "placements": "placements.csv",
    "skills": "skills.csv",
    "feedback": "feedback.csv",
    "interventions": "interventions.csv",
}

# Datasets with exactly one row per student; merged into one table.
FEATURE_DATASETS = [
    "academics", "attendance", "lms", "engagement", "placements", "skills", "feedback",
]
# Kept as an empty extension point for optional future label datasets.
LABEL_DATASETS: list[str] = []

# Values the CSV reader treats as "missing". NOTE: the text "None" is NOT in this
# list on purpose: in engagement.csv, club_participation = "None" is a real
# category meaning "no club participation" (pandas would otherwise turn it into NaN).
NA_VALUES = ["", "NA", "N/A", "NaN", "nan", "NULL", "null"]

# Schema per dataset:
#   required   - columns that must exist (otherwise the app refuses to start)
#   ranges     - numeric columns with (min, max) valid range; values outside
#                become "missing" and a warning is recorded
#   categories - text columns with the allowed values (case-insensitive match)
DATASET_SCHEMAS = {
    "students": {
        "required": ["student_id", "student_name", "department", "year_of_study",
                     "section", "admission_year", "student_email"],
        "ranges": {"year_of_study": (1, 8), "admission_year": (1990, 2100)},
        "categories": {},
    },
    "academics": {
        "required": ["student_id", "cgpa", "backlogs", "internal_score_pct", "semester_score_pct"],
        "ranges": {"cgpa": (0, 10), "backlogs": (0, 100),
                   "internal_score_pct": (0, 100), "semester_score_pct": (0, 100)},
        "categories": {},
    },
    "attendance": {
        "required": ["student_id", "overall_attendance_pct", "subjects_below_attendance_threshold"],
        "ranges": {"overall_attendance_pct": (0, 100), "subjects_below_attendance_threshold": (0, 100)},
        "categories": {},
    },
    "lms": {
        "required": ["student_id", "logins_last_30_days", "assignment_completion_pct",
                     "avg_weekly_learning_hours"],
        "ranges": {"logins_last_30_days": (0, 1000), "assignment_completion_pct": (0, 100),
                   "avg_weekly_learning_hours": (0, 168)},
        "categories": {},
    },
    "engagement": {
        "required": ["student_id", "events_attended", "hackathons_participated",
                     "club_participation", "volunteer_hours"],
        "ranges": {"events_attended": (0, 1000), "hackathons_participated": (0, 1000),
                   "volunteer_hours": (0, 10000)},
        "categories": {"club_participation": ["None", "Occasional", "Active"]},
    },
    "placements": {
        "required": ["student_id", "aptitude_score", "coding_score", "mock_interview_score",
                     "resume_readiness_pct", "placement_status"],
        "ranges": {"aptitude_score": (0, 100), "coding_score": (0, 100),
                   "mock_interview_score": (0, 100), "resume_readiness_pct": (0, 100)},
        "categories": {"placement_status": ["Not started", "Eligible", "Training", "Placed"]},
    },
    "skills": {
        "required": ["student_id", "technical_skill_score", "soft_skill_score",
                     "certifications_count", "projects_count"],
        "ranges": {"technical_skill_score": (0, 100), "soft_skill_score": (0, 100),
                   "certifications_count": (0, 1000), "projects_count": (0, 1000)},
        "categories": {},
    },
    "feedback": {
        "required": ["student_id", "student_satisfaction_1_to_5", "faculty_feedback_1_to_5",
                     "support_requested", "feedback_topic"],
        "ranges": {"student_satisfaction_1_to_5": (1, 5), "faculty_feedback_1_to_5": (1, 5)},
        "categories": {"support_requested": ["Yes", "No"]},
    },
    "interventions": {
        "required": ["intervention_id", "student_id", "intervention_type", "assigned_date",
                     "status", "follow_up_notes"],
        "ranges": {},
        "categories": {},  # validated for WRITES below; reads only warn
    },
}

# Allowed values when CREATING / UPDATING interventions (taken from the supplied dataset).
INTERVENTION_TYPES = [
    "Academic tutoring", "Aptitude training", "Attendance counselling",
    "Coding practice", "Mentoring", "Mock interview",
]
INTERVENTION_STATUSES = ["Recommended", "Assigned", "In progress", "Completed"]
OPEN_INTERVENTION_STATUSES = ["Recommended", "Assigned", "In progress"]
MAX_NOTES_LENGTH = 500

# --------------------------------------------------------------------------
# Student Success Score (0-100)  -  PRELIMINARY, needs faculty validation
# --------------------------------------------------------------------------
SCORE_CONFIG = {
    # Requested initial weights (must sum to 1.0)
    "overall_weights": {
        "academic": 0.40,
        "attendance": 0.20,
        "lms": 0.15,
        "placement_readiness": 0.25,
    },
    # If some inputs are missing, the remaining inputs are re-weighted. If less than
    # this share of the weight is available, the score is left EMPTY (null) instead
    # of guessing. Missing data is never treated as zero.
    "min_component_coverage": 0.5,
    "min_overall_coverage": 0.5,

    "academic": {
        "cgpa_scale_max": 10.0,                 # dataset README: CGPA is on a 0-10 scale
        "backlog_penalty_per_backlog": 20.0,    # 0 backlogs = 100, 5 or more = 0
        "weights": {"cgpa": 0.40, "semester_score": 0.25, "internal_score": 0.20, "backlogs": 0.15},
    },
    "attendance": {
        "penalty_per_subject_below_threshold": 5.0,   # points removed per short subject
        "weights": {"attendance": 1.0},
    },
    "lms": {
        "target_logins_30_days": 20,        # assumption: ~20 logins a month = full marks
        "target_weekly_learning_hours": 6,  # assumption: 6 h/week = full marks
        "weights": {"assignment_completion": 0.50, "logins": 0.25, "learning_hours": 0.25},
    },
    "placement_readiness": {
        "weights": {
            "aptitude": 0.20, "coding": 0.20, "mock_interview": 0.15,
            "resume": 0.15, "technical_skills": 0.20, "soft_skills": 0.10,
        },
    },
}

COMPONENT_LABELS = {
    "academic": "Academic",
    "attendance": "Attendance",
    "lms": "LMS activity",
    "placement_readiness": "Placement readiness",
}

# --------------------------------------------------------------------------
# Rule-based risk indicators  -  NOT probabilities, NOT for automated decisions
# --------------------------------------------------------------------------
# Rule format:
#   column      : column of the merged student table
#   direction   : "below"    -> triggered when value <  threshold
#                 "at_least" -> triggered when value >= threshold
#                 "equals"   -> triggered when value == `equals`
#   tiers       : strictest first; the first tier that matches gives its points
#   message     : text shown to faculty ({value} and {threshold} are filled in)
#   action      : supportive action suggested when the rule triggers
RISK_CONFIG = {
    "levels": {"medium_min_points": 4, "high_min_points": 7},
    # If fewer than this share of a student's indicators can be evaluated (because data is
    # missing) the level is "Insufficient data" instead of a misleading "Low".
    "min_evaluated_share": 0.5,
    "academic": {
        "rules": [
            {"id": "low_cgpa", "label": "CGPA", "column": "cgpa", "direction": "below",
             "tiers": [{"threshold": 5.5, "points": 3}, {"threshold": 6.5, "points": 1}],
             "message": "CGPA is {value:.2f} (below {threshold:g} on the 0-10 scale)",
             "action": "Arrange academic tutoring or a meeting with the faculty mentor"},
            {"id": "low_semester_score", "label": "Semester score", "column": "semester_score_pct",
             "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Semester score is {value:.1f}% (below {threshold:g}%)",
             "action": "Plan a structured revision schedule for upcoming exams"},
            {"id": "low_internal_score", "label": "Internal score", "column": "internal_score_pct",
             "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Internal assessment score is {value:.1f}% (below {threshold:g}%)",
             "action": "Review internal assessment feedback with the course faculty"},
            {"id": "backlogs", "label": "Backlogs", "column": "backlogs", "direction": "at_least",
             "tiers": [{"threshold": 3, "points": 3}, {"threshold": 1, "points": 1}],
             "message": "{value:g} backlog(s) recorded ({threshold:g} or more)",
             "action": "Build a backlog-clearing plan with exam dates and tutoring support"},
            {"id": "low_attendance", "label": "Attendance", "column": "overall_attendance_pct",
             "direction": "below",
             "tiers": [{"threshold": 65, "points": 3}, {"threshold": 75, "points": 1}],
             "message": "Overall attendance is {value:.1f}% (below {threshold:g}%)",
             "action": "Offer attendance counselling and find out what is blocking attendance"},
            {"id": "subjects_below_threshold", "label": "Subjects below attendance threshold",
             "column": "subjects_below_attendance_threshold", "direction": "at_least",
             "tiers": [{"threshold": 2, "points": 1}],
             "message": "Attendance is below the required threshold in {value:g} subjects",
             "action": "Prioritise catching up on the subjects with short attendance"},
            {"id": "low_assignment_completion", "label": "Assignment completion",
             "column": "assignment_completion_pct", "direction": "below",
             "tiers": [{"threshold": 50, "points": 2}, {"threshold": 70, "points": 1}],
             "message": "Assignment completion is {value:.1f}% (below {threshold:g}%)",
             "action": "Set up a weekly assignment checklist with a mentor check-in"},
            {"id": "support_requested", "label": "Support requested", "column": "support_requested",
             "direction": "equals", "equals": "Yes", "points": 1,
             "message": "Student asked for support (feedback topic: {topic})",
             "action": "Follow up on the student's own request for support"},
        ],
    },
    "placement": {
        "rules": [
            {"id": "low_aptitude", "label": "Aptitude", "column": "aptitude_score", "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Aptitude score is {value:.1f} (below {threshold:g})",
             "action": "Start a daily aptitude practice routine (quantitative, logical, verbal)"},
            {"id": "low_coding", "label": "Coding", "column": "coding_score", "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Coding score is {value:.1f} (below {threshold:g})",
             "action": "Follow a graded coding practice plan with regular problem-solving sessions"},
            {"id": "low_mock_interview", "label": "Mock interview", "column": "mock_interview_score",
             "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Mock interview score is {value:.1f} (below {threshold:g})",
             "action": "Schedule mock interviews with feedback from the placement team"},
            {"id": "low_resume", "label": "Resume readiness", "column": "resume_readiness_pct",
             "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Resume readiness is {value:.1f}% (below {threshold:g}%)",
             "action": "Get the resume reviewed and improved with the placement team"},
            {"id": "low_technical_skills", "label": "Technical skills", "column": "technical_skill_score",
             "direction": "below",
             "tiers": [{"threshold": 40, "points": 2}, {"threshold": 55, "points": 1}],
             "message": "Technical skill score is {value:.1f} (below {threshold:g})",
             "action": "Strengthen core technical skills through a guided course or lab practice"},
            {"id": "low_soft_skills", "label": "Soft skills", "column": "soft_skill_score",
             "direction": "below",
             "tiers": [{"threshold": 50, "points": 1}],
             "message": "Soft skill score is {value:.1f} (below {threshold:g})",
             "action": "Join a communication or group-discussion workshop"},
            {"id": "no_projects", "label": "Projects", "column": "projects_count", "direction": "below",
             "tiers": [{"threshold": 1, "points": 1}],
             "message": "No projects recorded yet",
             "action": "Start one small portfolio project (guided by a mentor)"},
            {"id": "support_requested", "label": "Support requested", "column": "support_requested",
             "direction": "equals", "equals": "Yes", "points": 1,
             "message": "Student asked for support (feedback topic: {topic})",
             "action": "Follow up on the student's own request for support"},
        ],
    },
}

RISK_LEVELS = ["Low", "Medium", "High"]
SPECIAL_RISK_LEVELS = ["Not applicable", "Insufficient data"]
ALL_RISK_LEVELS = RISK_LEVELS + SPECIAL_RISK_LEVELS
# Level that means "this student should be offered support"
SUPPORT_LEVELS = ["Medium", "High"]

# --------------------------------------------------------------------------
# Student segments (transparent rules, evaluated top to bottom, first match wins)
# --------------------------------------------------------------------------
SEGMENT_CONFIG = {
    "priority_score_below": 45,         # success score under this => Priority support
    "priority_high_risk_score_below": 55,  # any High risk AND score under this => Priority support
    "needs_support_score_below": 55,    # score under this, any High risk, or BOTH risks Medium+ => Needs support
    "high_readiness_min_score": 70,     # score at or above this (and no Medium/High risk)
}
SEGMENTS = ["High readiness", "Developing", "Needs support", "Priority support"]
SEGMENT_INSUFFICIENT = "Insufficient data"
SEGMENT_DESCRIPTIONS = {
    "Priority support": "Success score below {priority_score_below}, or a High risk level together "
                        "with a success score below {priority_high_risk_score_below}.",
    "Needs support": "Not Priority, but success score below {needs_support_score_below}, or a High "
                     "risk level, or Medium/High risk in BOTH academic and placement areas.",
    "High readiness": "Success score of {high_readiness_min_score} or more and no Medium/High risk.",
    "Developing": "Everyone else: no High risk, a success score of at least "
                  "{needs_support_score_below}, and either a score below {high_readiness_min_score} "
                  "or one Medium risk flag.",
    "Insufficient data": "Too many inputs are missing to calculate a success score.",
}

# Placement readiness at/above this counts as "strong placement readiness" on the dashboard.
STRONG_PLACEMENT_READINESS_MIN = 70

# --------------------------------------------------------------------------
# Recommendation thresholds
# --------------------------------------------------------------------------
REC_CONFIG = {
    "attendance_below": 75, "attendance_high_below": 65,
    "cgpa_below": 6.5, "cgpa_high_below": 5.5,
    "semester_below": 55, "internal_below": 55,
    "assignment_below": 70, "assignment_high_below": 50,
    "logins_below": 10, "weekly_hours_below": 3,
    "skill_below": 55, "skill_high_below": 40,   # aptitude/coding/mock/resume/technical
    "soft_skill_below": 50,
    "low_feedback_at_most": 2,
    "strong_readiness_min_score": 70,
}

# --------------------------------------------------------------------------
# CORS (React dev servers)
# --------------------------------------------------------------------------
CORS_ORIGINS = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
).split(",") if origin.strip()]
