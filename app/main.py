"""
Application entry point.

Run with:   uvicorn app.main:app --reload
Docs at:    http://127.0.0.1:8000/docs

All responses use one of two shapes:
  success: {"status": "success", "data": ..., "meta": {...}}
  error:   {"status": "error", "error": {"code": 404, "type": "not_found", "message": "...", "details": ...}}
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import CORS_ORIGINS
from .auth import init_auth_store, SECRET_KEY, DEFAULT_SECRET_WARNING
from .data_service import DataService, DataValidationError, PersistenceError
from .routers import analytics, dashboard, interventions, students, system, auth_routes, ai_chat
from .utils import clean

logger = logging.getLogger("smart_campus")

ERROR_TYPES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 422: "validation_error",
               500: "internal_error", 503: "service_unavailable"}


def error_response(status_code: int, message: str, details=None, error_type: str | None = None):
    body = {"status": "error",
            "error": {"code": status_code, "type": error_type or ERROR_TYPES.get(status_code, "error"),
                      "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=clean(body))


def create_app(data_dir: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if os.getenv("ENVIRONMENT", "development").lower() == "production" and SECRET_KEY == DEFAULT_SECRET_WARNING:
            raise RuntimeError("AUTH_SECRET_KEY must be set to a strong random value in production.")
        init_auth_store()
        if SECRET_KEY == DEFAULT_SECRET_WARNING:
            logger.warning("AUTH_SECRET_KEY is using the development fallback; set a strong secret before deployment.")
        app.state.service = None
        app.state.load_errors = []
        try:
            app.state.service = DataService(data_dir).load()
        except DataValidationError as exc:
            app.state.load_errors = exc.errors
            logger.error("Dataset validation failed: %s", "; ".join(exc.errors))
        except Exception:  # never crash on startup; report as unhealthy instead
            logger.exception("Unexpected error while loading datasets")
            app.state.load_errors = ["Unexpected error while loading datasets (see server log)."]
        yield

    app = FastAPI(
        title="Smart Campus Analytics API",
        version="1.0.0",
        description=("Prototype backend: unified student profiles, a transparent success score, "
                     "rule-based support indicators and dashboard analytics, computed from CSV files. "
                     "Uses a local JSON user store and CSV persistence. Protected API routes require JWT authentication."),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message", "Request failed")
            details = {k: v for k, v in detail.items() if k != "message"} or None
        else:
            message, details = str(detail), None
        return error_response(exc.status_code, message, details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p not in ("query", "path", "body")),
                    "message": e["msg"]} for e in exc.errors()]
        return error_response(422, "The request is invalid. Check the 'details' list.", details)

    @app.exception_handler(PersistenceError)
    async def persistence_error(_: Request, exc: PersistenceError):
        return error_response(500, str(exc), error_type="persistence_error")

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        logger.exception("Unhandled error")  # full traceback goes to the server log only
        return error_response(500, "Something went wrong on the server. Please try again later.")

    for router in (system.router, auth_routes.router, dashboard.router, students.router, analytics.router,
                   interventions.router, ai_chat.router):
        app.include_router(router)
    return app


app = create_app()
