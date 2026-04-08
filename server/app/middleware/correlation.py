"""Request-ID middleware. Reads X-Request-ID from inbound request,
generates one if absent, propagates it via contextvar, and echoes it on the
response. structlog picks it up via merge_contextvars.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from asgi_correlation_id import CorrelationIdMiddleware

if TYPE_CHECKING:
    from fastapi import FastAPI


def install(app: FastAPI) -> None:
    # Don't pass generator=None — that overrides the default uuid4 with None and
    # blows up the middleware. Omitting the kwarg keeps the default.
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name="X-Request-ID",
        update_request_header=True,
    )
