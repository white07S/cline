"""OpenTelemetry + Sentry initialization.

Call ``init_observability(app)`` in the FastAPI lifespan startup.
Call ``init_worker_observability()`` from non-FastAPI entry points (Dagster
code locations, scripts) so they get the same Sentry + OTEL pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging import get_logger
from app.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)


def _init_sentry() -> None:
    settings = get_settings()
    obs = settings.observability
    if not obs.sentry_enabled or obs.sentry_dsn is None:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=obs.sentry_dsn.get_secret_value(),
        environment=obs.sentry_environment,
        traces_sample_rate=obs.sentry_traces_sample_rate,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
            SqlalchemyIntegration(),
        ],
    )
    log.info("sentry_initialized", environment=obs.sentry_environment)


def _init_otel_tracing() -> None:
    settings = get_settings()
    if not settings.observability.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    resource = Resource.create(
        {
            "service.name": settings.app.name,
            "service.version": settings.app.version,
            "deployment.environment": settings.env,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.observability.otel_sample_rate),
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    log.info("otel_tracing_initialized")


def init_observability(app: FastAPI) -> None:
    """Initialize Sentry + OTEL for the FastAPI app. Call from lifespan startup."""
    _init_sentry()
    _init_otel_tracing()

    settings = get_settings()
    if not settings.observability.otel_enabled:
        return

    # Auto-instrument FastAPI, SQLAlchemy, httpx, redis. We do these explicitly
    # (not via opentelemetry-instrument CLI) to control ordering.
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    log.info("otel_instrumentation_applied", components=["fastapi", "httpx", "redis"])


def init_worker_observability() -> None:
    """Init OTEL + Sentry for non-FastAPI processes (Dagster code locations, scripts).

    No transport-specific instrumentation here — Dagster ships its own OTEL
    integration if enabled, and httpx/redis instrumentors are applied lazily by
    code that imports them.
    """
    _init_sentry()
    _init_otel_tracing()
