"""Health and readiness endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.settings import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    env: str
    timestamp: datetime


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe — always returns ok if the process can serve requests."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app.name,
        version=settings.app.version,
        env=settings.env,
        timestamp=datetime.now(UTC),
    )


@router.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Readiness probe — should also check downstream deps in a real impl."""
    # TODO: ping postgres, redis, qdrant. Raise on failure.
    settings = get_settings()
    return HealthResponse(
        status="ready",
        service=settings.app.name,
        version=settings.app.version,
        env=settings.env,
        timestamp=datetime.now(UTC),
    )
