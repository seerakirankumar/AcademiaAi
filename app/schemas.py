"""Request models (input validation for the endpoints that change data)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import INTERVENTION_STATUSES, INTERVENTION_TYPES, MAX_NOTES_LENGTH


def _match(value: str, allowed: list[str], field: str) -> str:
    lookup = {a.lower(): a for a in allowed}
    found = lookup.get(value.strip().lower())
    if found is None:
        raise ValueError(f"'{value}' is not a valid {field}. Allowed: {', '.join(allowed)}")
    return found


class InterventionCreate(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=32, examples=["STU20260001"])
    intervention_type: str = Field(..., examples=["Mentoring"])
    assigned_date: date | None = Field(None, description="YYYY-MM-DD; defaults to today")
    status: str = Field("Recommended", examples=["Assigned"])
    follow_up_notes: str = Field("", max_length=MAX_NOTES_LENGTH)

    @field_validator("intervention_type")
    @classmethod
    def _type(cls, v: str) -> str:
        return _match(v, INTERVENTION_TYPES, "intervention_type")

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _match(v, INTERVENTION_STATUSES, "status")

    @field_validator("follow_up_notes")
    @classmethod
    def _notes(cls, v: str) -> str:
        return v.strip().replace("\r", " ").replace("\n", " ")


class InterventionUpdate(BaseModel):
    status: str | None = None
    follow_up_notes: str | None = Field(None, max_length=MAX_NOTES_LENGTH)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        return None if v is None else _match(v, INTERVENTION_STATUSES, "status")

    @field_validator("follow_up_notes")
    @classmethod
    def _notes(cls, v: str | None) -> str | None:
        return None if v is None else v.strip().replace("\r", " ").replace("\n", " ")

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.status is None and self.follow_up_notes is None:
            raise ValueError("Provide at least one of 'status' or 'follow_up_notes'.")
        return self

# Admin-only student create/update models. Values are stored directly in the working CSV files.
from pydantic import ConfigDict


class StudentEditableFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_name: str | None = Field(None, min_length=1, max_length=120)
    department: str | None = Field(None, min_length=1, max_length=120)
    year_of_study: int | None = Field(None, ge=1, le=8)
    section: str | None = Field(None, min_length=1, max_length=8)
    admission_year: int | None = Field(None, ge=1990, le=2100)
    student_email: str | None = Field(None, max_length=254)
    cgpa: float | None = Field(None, ge=0, le=10)
    backlogs: int | None = Field(None, ge=0, le=100)
    internal_score_pct: float | None = Field(None, ge=0, le=100)
    semester_score_pct: float | None = Field(None, ge=0, le=100)
    overall_attendance_pct: float | None = Field(None, ge=0, le=100)
    subjects_below_attendance_threshold: int | None = Field(None, ge=0, le=100)
    logins_last_30_days: int | None = Field(None, ge=0, le=1000)
    assignment_completion_pct: float | None = Field(None, ge=0, le=100)
    avg_weekly_learning_hours: float | None = Field(None, ge=0, le=168)
    events_attended: int | None = Field(None, ge=0, le=1000)
    hackathons_participated: int | None = Field(None, ge=0, le=1000)
    club_participation: str | None = None
    volunteer_hours: float | None = Field(None, ge=0, le=10000)
    aptitude_score: float | None = Field(None, ge=0, le=100)
    coding_score: float | None = Field(None, ge=0, le=100)
    mock_interview_score: float | None = Field(None, ge=0, le=100)
    resume_readiness_pct: float | None = Field(None, ge=0, le=100)
    placement_status: str | None = None
    technical_skill_score: float | None = Field(None, ge=0, le=100)
    soft_skill_score: float | None = Field(None, ge=0, le=100)
    certifications_count: int | None = Field(None, ge=0, le=1000)
    projects_count: int | None = Field(None, ge=0, le=1000)
    student_satisfaction_1_to_5: float | None = Field(None, ge=1, le=5)
    faculty_feedback_1_to_5: float | None = Field(None, ge=1, le=5)
    support_requested: str | None = None
    feedback_topic: str | None = Field(None, max_length=120)

    @field_validator("club_participation")
    @classmethod
    def _club(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _match(value, ["None", "Occasional", "Active"], "club_participation")

    @field_validator("placement_status")
    @classmethod
    def _placement(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _match(value, ["Not started", "Eligible", "Training", "Placed"], "placement_status")

    @field_validator("support_requested")
    @classmethod
    def _support(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _match(value, ["Yes", "No"], "support_requested")

    @field_validator("student_email")
    @classmethod
    def _email_shape(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return value.strip()


class StudentCreate(StudentEditableFields):
    student_id: str | None = Field(None, pattern=r"^STU[0-9]{8}$")
    student_name: str = Field(..., min_length=1, max_length=120)
    department: str = Field(..., min_length=1, max_length=120)
    year_of_study: int = Field(..., ge=1, le=8)
    section: str = Field(..., min_length=1, max_length=8)
    admission_year: int = Field(..., ge=1990, le=2100)


class StudentUpdate(StudentEditableFields):
    @model_validator(mode="after")
    def _at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self
