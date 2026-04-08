"""slowapi rate limiting. Per-route limits are applied via decorators in routers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{_settings.ratelimit.default_per_minute}/minute"],
    storage_uri=f"{_settings.redis.url}/{_settings.redis.ratelimit_db}",
)


def install(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
