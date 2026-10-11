"""Student list, unified profile, score, recommendations and risk records."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from .. import profile_service
from ..config import ALL_RISK_LEVELS, SEGMENTS, SEGMENT_INSUFFICIENT
from ..data_service import DataService, NotFoundError
from ..deps import get_service, not_found
from ..auth import require_roles
from ..utils import normalize_choice, success
from ..schemas import StudentCreate, StudentUpdate

router = APIRouter(prefix="/api", tags=["Students"], dependencies=[Depends(require_roles("admin", "faculty", "placement_officer"))])

StudentId = Path(..., pattern=r"^[A-Za-z0-9_-]{1,32}$", description="e.g. STU20260001", examples=["STU20260001"])

SORT_FIELDS = {
    "student_id": "student_id", "name": "student_name", "department": "department",
    "success_score": "success_score", "cgpa": "cgpa", "attendance": "overall_attendance_pct",
}


def _department_filter(service: DataService, value: str | None) -> str | None:
    if not value:
        return None
    match = service.match_department(value)
    if match is None:
        raise HTTPException(422, detail={"message": f"Unknown department '{value}'.",
                                         "allowed_values": service.departments()})
    return match


@router.get("/students", summary="Student list with search, filters and pagination")
def list_students(
    search: str | None = Query(None, max_length=100, description="Part of a student ID or name"),
    department: str | None = Query(None, description="e.g. CSE"),
    year: int | None = Query(None, ge=1, le=8, description="Year of study"),
    section: str | None = Query(None, max_length=5),
    academic_risk: str | None = Query(None, description="Low | Medium | High | Not applicable | Insufficient data"),
    placement_risk: str | None = Query(None, description="Low | Medium | High | Not applicable | Insufficient data"),
    segment: str | None = Query(None, description="High readiness | Developing | Needs support | Priority support"),
    placement_status: str | None = Query(None, description="Not started | Eligible | Training | Placed"),
    sort_by: str = Query("student_id", description=f"One of: {', '.join(SORT_FIELDS)}"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: DataService = Depends(get_service),
):
    df = service.students
    dept = _department_filter(service, department)
    academic_risk = normalize_choice(academic_risk, ALL_RISK_LEVELS, "academic_risk")
    placement_risk = normalize_choice(placement_risk, ALL_RISK_LEVELS, "placement_risk")
    segment = normalize_choice(segment, SEGMENTS + [SEGMENT_INSUFFICIENT], "segment")
    placement_status = normalize_choice(
        placement_status, sorted(df["placement_status"].dropna().unique()), "placement_status")
    sort_key = normalize_choice(sort_by, list(SORT_FIELDS), "sort_by")

    if search:
        q = search.strip()
        df = df[df["student_id"].str.contains(q, case=False, regex=False)
                | df["student_name"].str.contains(q, case=False, regex=False)]
    if dept:
        df = df[df["department"] == dept]
    if year is not None:
        df = df[df["year_of_study"] == year]
    if section:
        df = df[df["section"].str.upper() == section.strip().upper()]
    if academic_risk:
        df = df[df["academic_risk_level"] == academic_risk]
    if placement_risk:
        df = df[df["placement_risk_level"] == placement_risk]
    if segment:
        df = df[df["segment"] == segment]
    if placement_status:
        df = df[df["placement_status"] == placement_status]

    df = df.sort_values([SORT_FIELDS[sort_key], "student_id"], ascending=[order == "asc", True],
                        na_position="last")
    total = len(df)
    page = df.iloc[offset: offset + limit]
    items = [profile_service.list_item(r) for r in page.to_dict("records")]
    return success(items, {"total": total, "count": len(items), "limit": limit, "offset": offset,
                           "has_more": offset + len(items) < total})


@router.get("/students/{student_id}", summary="Unified student profile")
def student_profile(student_id: str = StudentId, service: DataService = Depends(get_service)):
    try:
        return success(profile_service.build_profile(service, student_id))
    except NotFoundError as exc:
        raise not_found(exc)


@router.post("/students", summary="Add a student (admin only)", status_code=201,
             dependencies=[Depends(require_roles("admin"))])
def create_student(body: StudentCreate, service: DataService = Depends(get_service)):
    try:
        values = body.model_dump(exclude_none=True)
        row = service.create_student(values)
        return success(profile_service.build_profile(service, row["student_id"]))
    except ValueError as exc:
        raise HTTPException(409 if "already exists" in str(exc) else 422,
                            detail={"message": str(exc)}) from exc


@router.patch("/students/{student_id}", summary="Update a student (admin only)",
              dependencies=[Depends(require_roles("admin"))])
def update_student(body: StudentUpdate, student_id: str = StudentId,
                   service: DataService = Depends(get_service)):
    try:
        row = service.update_student(student_id, body.model_dump(exclude_unset=True))
        return success(profile_service.build_profile(service, row["student_id"]))
    except NotFoundError as exc:
        raise not_found(exc)
    except ValueError as exc:
        raise HTTPException(422, detail={"message": str(exc)}) from exc


@router.get("/students/{student_id}/score", summary="Score breakdown and formula")
def student_score(student_id: str = StudentId, service: DataService = Depends(get_service)):
    try:
        return success(profile_service.score_breakdown(service, student_id))
    except NotFoundError as exc:
        raise not_found(exc)


@router.get("/students/{student_id}/recommendations", summary="Personalised recommendations")
def student_recommendations(student_id: str = StudentId, service: DataService = Depends(get_service)):
    try:
        return success(profile_service.recommendations_for(service, student_id))
    except NotFoundError as exc:
        raise not_found(exc)


@router.get("/risks", summary="Academic and placement risk records (rule-based, not probabilities)")
def risks(
    academic_level: str | None = Query(None, description="Low | Medium | High | Not applicable | Insufficient data"),
    placement_level: str | None = Query(None, description="Low | Medium | High | Not applicable | Insufficient data"),
    department: str | None = Query(None),
    year: int | None = Query(None, ge=1, le=8),
    segment: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: DataService = Depends(get_service),
):
    df = service.students
    academic_level = normalize_choice(academic_level, ALL_RISK_LEVELS, "academic_level")
    placement_level = normalize_choice(placement_level, ALL_RISK_LEVELS, "placement_level")
    segment = normalize_choice(segment, SEGMENTS + [SEGMENT_INSUFFICIENT], "segment")
    dept = _department_filter(service, department)
    if academic_level:
        df = df[df["academic_risk_level"] == academic_level]
    if placement_level:
        df = df[df["placement_risk_level"] == placement_level]
    if dept:
        df = df[df["department"] == dept]
    if year is not None:
        df = df[df["year_of_study"] == year]
    if segment:
        df = df[df["segment"] == segment]

    # Most points first (highest need for support), then by ID for a stable order.
    df = df.assign(_total=df["academic_risk_points"] + df["placement_risk_points"])
    df = df.sort_values(["_total", "student_id"], ascending=[False, True])
    total = len(df)
    page = df.iloc[offset: offset + limit]
    items = [profile_service.risk_item(r, service.risk_details[r["student_id"]]) for r in page.to_dict("records")]
    return success(items, {
        "total": total, "count": len(items), "limit": limit, "offset": offset,
        "has_more": offset + len(items) < total,
        "sorted_by": "academic + placement risk points, highest first",
        "disclaimer": "Rule-based indicators, not probabilities. Use only to offer support.",
    })
