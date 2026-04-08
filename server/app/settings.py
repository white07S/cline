"""Typed application settings.

Loads in this order, with later sources overriding earlier:
  1. configs/server.yml          (committed defaults)
  2. configs/server.{env}.yml    (env-specific overrides; env from APP_ENV)
  3. Environment variables       (always wins; secrets live here)

There is no untyped config access anywhere in the codebase. Every field
below is typed and validated. Add new fields here when you add new YAML keys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Sub-models ──────────────────────────────────────────────────


class AppMeta(BaseModel):
    name: str = "data-platform"
    version: str = "0.1.0"


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    max_body_size_mb: int = 50


class CorsSettings(BaseModel):
    allow_origins: list[str] = Field(default_factory=list)
    allow_credentials: bool = True
    allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class DatabaseSettings(BaseModel):
    url: PostgresDsn
    url_sync: PostgresDsn  # used by alembic + celery result backend
    pool_size: int = 10
    max_overflow: int = 5
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 1800
    echo: bool = False


class RedisSettings(BaseModel):
    url: RedisDsn
    cache_db: int = 1
    celery_broker_db: int = 0
    ratelimit_db: int = 2
    default_ttl_seconds: int = 300


class RateLimitSettings(BaseModel):
    default_per_minute: int = 60
    auth_per_minute: int = 10


class ObservabilitySettings(BaseModel):
    otel_enabled: bool = True
    otel_sample_rate: float = 1.0
    prometheus_enabled: bool = True
    sentry_enabled: bool = False
    sentry_dsn: SecretStr | None = None
    sentry_environment: str = "dev"
    sentry_traces_sample_rate: float = 1.0


class LoggingSettings(BaseModel):
    level: str = "INFO"
    json: bool = True
    include_trace_id: bool = True


class QdrantSettings(BaseModel):
    url: str
    api_key: SecretStr | None = None
    prefer_grpc: bool = True
    timeout_seconds: int = 30


class OpenAISettings(BaseModel):
    api_key: SecretStr
    chat_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072
    default_temperature: float = 0.2
    default_max_tokens: int = 2048
    default_timeout_seconds: int = 60
    max_concurrent_calls: int = 8


class AzureAuthSettings(BaseModel):
    tenant_id: str | None = None
    client_id: str | None = None
    api_audience: str | None = None


# ── Top-level Settings ──────────────────────────────────────────


class Settings(BaseSettings):
    """Top-level settings — loaded from YAML + env vars."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=None,  # docker compose injects .env; we don't double-load.
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["dev", "prod", "test"] = "dev"

    app: AppMeta = AppMeta()
    server: ServerSettings = ServerSettings()
    cors: CorsSettings = CorsSettings()
    database: DatabaseSettings
    redis: RedisSettings
    ratelimit: RateLimitSettings = RateLimitSettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    logging: LoggingSettings = LoggingSettings()
    qdrant: QdrantSettings
    openai: OpenAISettings
    azure: AzureAuthSettings = AzureAuthSettings()


# ── Loader ──────────────────────────────────────────────────────


def _read_yaml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        loaded = yaml.safe_load(f)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise TypeError(f"{path} must contain a YAML mapping at the top level, got {type(loaded)}")
    return loaded


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """Merge nested dicts; override wins on conflict."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def _resolve_configs_dir() -> Path:
    """Resolve the configs directory.

    Order:
      1. CONFIG_DIR env var (used by Docker, where source is mounted at /app)
      2. <repo_root>/configs derived from this file's location (local dev)
    """
    if env_dir := os.environ.get("CONFIG_DIR"):
        return Path(env_dir)
    return Path(__file__).resolve().parents[2] / "configs"


def _build_settings_dict() -> dict[str, object]:
    """Build the raw settings dict from YAML files. Env overrides applied later by pydantic."""
    configs_dir = _resolve_configs_dir()
    env_name = os.environ.get("APP_ENV", "dev")

    base = _read_yaml(configs_dir / "server.yml")
    override = _read_yaml(configs_dir / f"server.{env_name}.yml")
    merged = _deep_merge(base, override)

    # Inject secrets from env that aren't in YAML.
    merged["env"] = env_name
    merged.setdefault("database", {})
    merged["database"]["url"] = os.environ["DATABASE_URL"]  # type: ignore[index]
    merged["database"]["url_sync"] = os.environ["DATABASE_URL_SYNC"]  # type: ignore[index]

    merged.setdefault("redis", {})
    merged["redis"]["url"] = os.environ["REDIS_URL"]  # type: ignore[index]

    merged.setdefault("qdrant", {})
    merged["qdrant"]["url"] = os.environ["QDRANT_URL"]  # type: ignore[index]
    merged["qdrant"]["api_key"] = os.environ.get("QDRANT_API_KEY") or None  # type: ignore[index]

    merged.setdefault("openai", {})
    merged["openai"]["api_key"] = os.environ["OPENAI_API_KEY"]  # type: ignore[index]

    obs = merged.setdefault("observability", {})
    if isinstance(obs, dict):
        if dsn := os.environ.get("SENTRY_DSN"):
            obs["sentry_dsn"] = dsn
        if env := os.environ.get("SENTRY_ENVIRONMENT"):
            obs["sentry_environment"] = env
        if rate := os.environ.get("SENTRY_TRACES_SAMPLE_RATE"):
            obs["sentry_traces_sample_rate"] = float(rate)

    azure = merged.setdefault("azure", {})
    if isinstance(azure, dict):
        if tid := os.environ.get("AZURE_TENANT_ID"):
            azure["tenant_id"] = tid
        if cid := os.environ.get("AZURE_CLIENT_ID"):
            azure["client_id"] = cid
        if aud := os.environ.get("AZURE_API_AUDIENCE"):
            azure["api_audience"] = aud

    return merged


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Call this everywhere — never read env directly."""
    return Settings(**_build_settings_dict())  # type: ignore[arg-type]
