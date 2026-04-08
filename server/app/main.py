"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.db.base import dispose_engine
from app.logging import configure_logging, get_logger
from app.middleware import correlation, ratelimit
from app.observability import init_observability
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    configure_logging()
    init_observability(app)

    log = get_logger(__name__)
    settings = get_settings()
    log.info(
        "app_starting",
        env=settings.env,
        version=settings.app.version,
        otel_enabled=settings.observability.otel_enabled,
        sentry_enabled=settings.observability.sentry_enabled,
    )

    # Ensure Qdrant collections exist. Lazy import to keep app startup fast
    # if the vector store is unavailable in dev (warn, don't crash).
    try:
        from app.vectorstore.qdrant import ensure_collections

        await ensure_collections()
    except Exception:
        log.exception("qdrant_init_failed_continuing")

    yield

    log.info("app_stopping")
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        lifespan=lifespan,
    )

    # Order matters: correlation ID first, then CORS, then rate limit.
    correlation.install(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
    )

    ratelimit.install(app)

    if settings.observability.prometheus_enabled:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["observability"])

    app.include_router(api_router)

    return app


app = create_app()
