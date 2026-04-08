"""Celery app — broker on Redis, result backend on Postgres.

Imports observability init at module load so workers get OTEL + Sentry.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from celery import Celery

from app.logging import configure_logging
from app.observability import init_celery_observability
from app.settings import get_settings


def _redis_url_with_db(url: str, db: int) -> str:
    """Replace the path of a redis:// URL with the given DB number.

    Pydantic's RedisDsn canonicalises `redis://host:port` to include a path
    like `/0`, so naive f-string concatenation produces `/0/0`. We rebuild
    the URL explicitly to keep this safe regardless of the input shape.
    """
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{db}"))


# Configure logging + observability before any task module is imported.
configure_logging()
init_celery_observability()

_settings = get_settings()

celery_app = Celery(
    "data_platform",
    broker=_redis_url_with_db(str(_settings.redis.url), _settings.redis.celery_broker_db),
    # Celery's DB result backend speaks sync DSN.
    backend=f"db+{_settings.database.url_sync}",
    include=[
        # Add task modules here as you create them.
        # "app.workers.tasks.ingest",
        # "app.workers.tasks.pipelines",
        # "app.workers.tasks.embeddings",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    result_expires=86400,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
        "pipelines": {"exchange": "pipelines", "routing_key": "pipelines"},
        "embeddings": {"exchange": "embeddings", "routing_key": "embeddings"},
    },
    task_routes={
        "app.workers.tasks.ingest.*": {"queue": "ingestion"},
        "app.workers.tasks.pipelines.*": {"queue": "pipelines"},
        "app.workers.tasks.embeddings.*": {"queue": "embeddings"},
    },
)
