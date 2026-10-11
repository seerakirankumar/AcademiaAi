"""Department comparisons, trends and segments."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import analytics_service
from ..data_service import DataService
from ..deps import get_service
from ..auth import require_roles
from ..utils import success

router = APIRouter(prefix="/api", tags=["Analytics"], dependencies=[Depends(require_roles("admin", "faculty", "placement_officer", "judge_demo"))])


@router.get("/analytics/departments", summary="Department-wise metrics")
def departments(service: DataService = Depends(get_service)):
    rows = analytics_service.department_metrics(service)
    return success(rows, {"count": len(rows)})


@router.get("/analytics/trends", summary="Whether historical trend data exists")
def trends(service: DataService = Depends(get_service)):
    return success(analytics_service.trends(service))


@router.get("/segments", summary="Student segment summaries")
def segments(service: DataService = Depends(get_service)):
    rows = analytics_service.segment_summaries(service)
    return success(rows, {"count": len(rows), "total_students": int(len(service.students))})
