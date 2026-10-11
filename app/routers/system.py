"""Welcome, health and metadata endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from .. import analytics_service
from ..data_service import DataService
from ..deps import get_service
from ..utils import clean, success

router = APIRouter(tags=["System"])


@router.get("/", summary="API welcome information")
def root():
    return success({
        "name": "Smart Campus Analytics API",
        "version": "1.0.0",
        "description": "Prototype backend for student success analytics with CSV-backed data.",
        "docs": "/docs",
        "health": "/api/health",
        "authentication": "JWT bearer tokens required for protected API routes.",
    })


@router.get("/api/health", summary="Service health and loaded dataset status")
def health(request: Request):
    service: DataService | None = getattr(request.app.state, "service", None)
    if service is None:
        errors = getattr(request.app.state, "load_errors", [])
        return JSONResponse(status_code=503, content=clean({
            "status": "error",
            "data": {"service": "unhealthy", "datasets_loaded": False, "errors": errors},
            "meta": {}}))
    return success({"service": "healthy", "datasets_loaded": True, **service.health()})


@router.get("/api/metadata", summary="Departments, years, risk levels and dataset information")
def metadata(service: DataService = Depends(get_service)):
    return success(analytics_service.metadata(service))
