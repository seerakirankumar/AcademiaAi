"""FastAPI dependencies shared by the routers."""
from __future__ import annotations

from fastapi import HTTPException, Request

from .data_service import DataService, NotFoundError


def get_service(request: Request) -> DataService:
    """Return the loaded DataService, or answer 503 if the datasets failed validation."""
    service = getattr(request.app.state, "service", None)
    if service is None:
        errors = getattr(request.app.state, "load_errors", [])
        raise HTTPException(
            status_code=503,
            detail={"message": "The datasets could not be loaded, so analytics are unavailable. "
                               "See /api/health for details.",
                    "errors": errors},
        )
    return service


def not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))
