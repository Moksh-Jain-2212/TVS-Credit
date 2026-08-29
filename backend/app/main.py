"""FastAPI entrypoint for the NADI backend."""

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.env import load_backend_env

load_backend_env()

from app import models  # noqa: F401
from app.api import admin as admin_routes
from app.api import auth as auth_routes
from app.api import user_applications
from app.api.routes import router
from app.core.app_database import app_database_path, app_database_is_healthy, ensure_app_database
from app.services.risk_model_service import risk_model_service


logger = logging.getLogger("nadi")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_app_database()
    yield


app = FastAPI(
    title="TVS NADI",
    description="Adaptive Credit Path Engine backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"request_id": request_id, "path": request.url.path})
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    code = str(exc.detail).upper().replace(" ", "_")[:80] if isinstance(exc.detail, str) else "REQUEST_FAILED"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": {"code": code, "message": exc.detail if isinstance(exc.detail, str) else "Request failed"}},
        headers=exc.headers,
    )

app.include_router(router)
app.include_router(auth_routes.router)
app.include_router(user_applications.router)
app.include_router(admin_routes.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple service health response."""
    return {"status": "ok"}


@app.get("/ready")
def readiness_check() -> dict:
    """Return runtime dependency readiness without exposing secrets."""
    db_path = app_database_path()
    database_ok = app_database_is_healthy(db_path)
    model = risk_model_service.health()
    ready = database_ok
    return {
        "status": "ready" if ready else "not_ready",
        "database": {"ok": database_ok, "path": str(db_path)},
        "risk_model": model,
    }
