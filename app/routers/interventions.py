"""Intervention history (read) plus validated create/update with real CSV persistence."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..config import INTERVENTION_STATUSES, INTERVENTION_TYPES
from ..data_service import DataService, NotFoundError
from ..deps import get_service, not_found
from ..auth import require_roles
from ..schemas import InterventionCreate, InterventionUpdate
from ..utils import normalize_choice, success

router = APIRouter(prefix="/api/interventions", tags=["Interventions"], dependencies=[Depends(require_roles("admin", "faculty", "placement_officer"))])


@router.get("", summary="Intervention history with filtering")
def list_interventions(
    student_id: str | None = Query(None, pattern=r"^[A-Za-z0-9_-]{1,32}$"),
    status: str | None = Query(None, description="Recommended | Assigned | In progress | Completed"),
    intervention_type: str | None = Query(None),
    date_from: date | None = Query(None, description="YYYY-MM-DD"),
    date_to: date | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: DataService = Depends(get_service),
):
    status = normalize_choice(status, INTERVENTION_STATUSES, "status")
    intervention_type = normalize_choice(intervention_type, INTERVENTION_TYPES, "intervention_type")
    if student_id and not service.has_student(student_id):
        raise HTTPException(404, detail=f"Student '{student_id}' was not found.")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, detail="'date_from' must not be after 'date_to'.")
    records, status_counts = service.list_interventions(student_id, status, intervention_type,
                                                       date_from, date_to)
    total = len(records)
    items = records[offset: offset + limit]
    return success(items, {"total": total, "count": len(items), "limit": limit, "offset": offset,
                           "has_more": offset + len(items) < total, "status_counts": status_counts})


@router.post("", status_code=201, summary="Record a new intervention (saved to interventions.csv)")
def create_intervention(body: InterventionCreate, service: DataService = Depends(get_service)):
    try:
        record = service.add_intervention(body.student_id, body.intervention_type,
                                          body.assigned_date or date.today(), body.status,
                                          body.follow_up_notes)
    except NotFoundError as exc:
        raise not_found(exc)
    return success(record, {"persisted": True})


@router.patch("/{intervention_id}", summary="Update an intervention's status or notes (saved to CSV)")
def update_intervention(
    body: InterventionUpdate,
    intervention_id: str = Path(..., pattern=r"^[A-Za-z0-9_-]{1,32}$", examples=["INT0001"]),
    service: DataService = Depends(get_service),
):
    try:
        record = service.update_intervention(intervention_id, body.status, body.follow_up_notes)
    except NotFoundError as exc:
        raise not_found(exc)
    return success(record, {"persisted": True})
