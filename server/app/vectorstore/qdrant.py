"""Async Qdrant client wrapper.

Pydantic models all the way through — no dict[str, Any]. Collection definitions
are read from configs/qdrant.yml at startup and applied (idempotent create-if-missing).
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from app.logging import get_logger
from app.settings import get_settings

log = get_logger(__name__)


# ── Domain models for the wrapper ───────────────────────────────


class HnswConfig(BaseModel):
    m: int = 16
    ef_construct: int = 128
    full_scan_threshold: int = 10000


class CollectionConfig(BaseModel):
    name: str
    dim: int = Field(gt=0)
    distance: str = "Cosine"
    on_disk_payload: bool = True
    hnsw: HnswConfig = HnswConfig()


class QdrantConfigFile(BaseModel):
    prefer_grpc: bool = True
    timeout_seconds: int = 30
    collections: list[CollectionConfig] = Field(default_factory=list)


# ── Errors ──────────────────────────────────────────────────────


class VectorStoreError(Exception):
    """Base for vector store failures."""


# ── Loader ──────────────────────────────────────────────────────


def _load_qdrant_config() -> QdrantConfigFile:
    """Load configs/qdrant.yml. Fails loudly if missing or malformed."""
    from app.settings import _resolve_configs_dir

    path = _resolve_configs_dir() / "qdrant.yml"
    with path.open("rb") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise VectorStoreError("configs/qdrant.yml: top-level must be a mapping")
    section = raw.get("qdrant", {})
    if not isinstance(section, dict):
        raise VectorStoreError("configs/qdrant.yml: 'qdrant' key must be a mapping")
    return QdrantConfigFile(**section)


# ── Client ──────────────────────────────────────────────────────


def build_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(
        url=settings.qdrant.url,
        api_key=(settings.qdrant.api_key.get_secret_value() if settings.qdrant.api_key else None),
        prefer_grpc=settings.qdrant.prefer_grpc,
        timeout=settings.qdrant.timeout_seconds,
    )


_DISTANCE_MAP: dict[str, qmodels.Distance] = {
    "Cosine": qmodels.Distance.COSINE,
    "Dot": qmodels.Distance.DOT,
    "Euclid": qmodels.Distance.EUCLID,
}


async def ensure_collections() -> None:
    """Idempotent — create collections that don't exist. Never modifies existing."""
    client = build_client()
    cfg = _load_qdrant_config()

    try:
        existing = await client.get_collections()
    except UnexpectedResponse as e:
        log.exception("qdrant_list_collections_failed")
        raise VectorStoreError(f"Could not list Qdrant collections: {e}") from e

    existing_names = {c.name for c in existing.collections}

    for coll in cfg.collections:
        if coll.name in existing_names:
            log.info("qdrant_collection_exists", name=coll.name)
            continue

        distance = _DISTANCE_MAP.get(coll.distance)
        if distance is None:
            raise VectorStoreError(
                f"Unknown distance '{coll.distance}' for collection '{coll.name}'"
            )

        await client.create_collection(
            collection_name=coll.name,
            vectors_config=qmodels.VectorParams(size=coll.dim, distance=distance),
            on_disk_payload=coll.on_disk_payload,
            hnsw_config=qmodels.HnswConfigDiff(
                m=coll.hnsw.m,
                ef_construct=coll.hnsw.ef_construct,
                full_scan_threshold=coll.hnsw.full_scan_threshold,
            ),
        )
        log.info("qdrant_collection_created", name=coll.name, dim=coll.dim)
