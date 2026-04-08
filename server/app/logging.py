"""structlog setup. Routes both structlog and stdlib logs through one pipeline.

Dev: pretty ConsoleRenderer.
Prod: JSONL one-line-per-event, ready for promtail → Loki.
"""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog
from structlog.types import EventDict, Processor

from app.settings import get_settings


def _add_otel_trace_id(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """Pull the current OTEL trace_id and span_id into the log record, if any."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except ImportError:  # pragma: no cover - OTEL is required, but handle gracefully
        pass
    return event_dict


def configure_logging() -> None:
    """Wire structlog + stdlib together. Idempotent."""
    settings = get_settings()
    level = logging.getLevelName(settings.logging.level.upper())

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.logging.include_trace_id:
        shared_processors.append(_add_otel_trace_id)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Renderer for the stdlib formatter — used by both structlog and stdlib loggers.
    renderer: Processor
    if settings.logging.json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Reset handlers — important for hot reload + tests.
    root.handlers = [handler]
    root.setLevel(level)

    # Tame chatty libs (also configurable via configs/logging.yml — kept here as defaults).
    for name, lvl in (
        ("uvicorn", "INFO"),
        ("uvicorn.error", "INFO"),
        ("uvicorn.access", "WARNING"),
        ("sqlalchemy.engine", "WARNING"),
        ("dagster", "INFO"),
        ("httpx", "WARNING"),
    ):
        logging.getLogger(name).setLevel(logging.getLevelName(lvl))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger. Use module __name__ as the name."""
    return cast("structlog.stdlib.BoundLogger", structlog.stdlib.get_logger(name))
