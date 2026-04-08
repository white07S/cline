"""Top-level Dagster Definitions object.

Loaded by both `dagster-webserver` and `dagster-daemon` via:
    -m app.orchestration.definitions

Single source of truth — every asset, job, schedule, sensor, and resource
the platform exposes must be wired in here.
"""

from __future__ import annotations

from dagster import Definitions, load_assets_from_modules

from app.logging import configure_logging
from app.observability import init_worker_observability
from app.orchestration.assets import example
from app.orchestration.resources import S3Resource

# Make sure structlog and OTEL are wired before Dagster touches anything.
# Both functions are idempotent.
configure_logging()
init_worker_observability()


all_assets = load_assets_from_modules([example])

defs = Definitions(
    assets=all_assets,
    resources={
        "s3": S3Resource(),
    },
)
