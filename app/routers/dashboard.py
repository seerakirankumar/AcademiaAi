"""Dashboard KPIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import analytics_service
from ..data_service import DataService
from ..deps import get_service
from ..auth import require_roles
from ..utils import success

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(require_roles("admin", "faculty", "placement_officer", "judge_demo"))])


@router.get("/summary", summary="Dashboard KPIs calculated from the CSV data")
def summary(service: DataService = Depends(get_service)):
    return success(analytics_service.dashboard_summary(service))
