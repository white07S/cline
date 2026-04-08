"""Async S3 wrapper.

- All inputs/outputs are typed Pydantic models — no `dict[str, Any]` leaks.
- Botocore exceptions are wrapped into `S3Error` subclasses at the boundary so
  callers can `except S3Error` without importing botocore.
- Connections are managed via context-manager methods. The wrapper itself is
  cheap to instantiate; reuse it via dependency injection rather than building
  it inside hot loops.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING

import aioboto3
from aiobotocore.config import AioConfig
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel

from app.logging import get_logger
from app.settings import S3Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)


# ── Domain models ───────────────────────────────────────────────


class ObjectMetadata(BaseModel):
    """Metadata returned by head_object / list_objects, in a typed shape."""

    bucket: str
    key: str
    size: int
    etag: str
    last_modified: datetime
    content_type: str | None = None


# ── Errors ──────────────────────────────────────────────────────


class S3Error(Exception):
    """Base for object-store failures."""


class S3NotFoundError(S3Error):
    """Raised when an object or bucket does not exist."""


class S3AccessError(S3Error):
    """Raised when credentials are missing/invalid or the caller is not authorized."""


def _wrap(err: BaseException, *, bucket: str, key: str | None = None) -> S3Error:
    """Translate a botocore error into a typed domain error.

    Returns the wrapped error — callers are responsible for the actual
    `raise ... from err` so the chain stays explicit at the call site.
    `key` is optional because some operations (head_bucket) only have a bucket.
    """
    target = f"s3://{bucket}/{key or ''}"
    if isinstance(err, ClientError):
        code = err.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "NoSuchBucket", "404"}:
            return S3NotFoundError(f"{target} not found")
        if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "403"}:
            return S3AccessError(f"{target} access denied")
    if isinstance(err, BotoCoreError):
        return S3Error(f"{target} botocore error: {err}")
    return S3Error(f"{target} unexpected error: {err}")


# ── Client ──────────────────────────────────────────────────────


class S3Client:
    """Thin async wrapper around aioboto3.

    Hold one of these at the application level (e.g., FastAPI dependency or
    Dagster resource) — do NOT instantiate per-request.
    """

    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session()
        self._boto_config = AioConfig(
            signature_version="s3v4",
            s3={"addressing_style": settings.addressing_style},
            retries={"max_attempts": 5, "mode": "standard"},
        )

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[object]:
        """Yield an aioboto3 s3 client. Wrapped so we control credential plumbing."""
        async with self._session.client(
            "s3",
            endpoint_url=self._settings.endpoint_url,
            region_name=self._settings.region,
            aws_access_key_id=self._settings.access_key_id.get_secret_value(),
            aws_secret_access_key=self._settings.secret_access_key.get_secret_value(),
            use_ssl=self._settings.use_ssl,
            config=self._boto_config,
        ) as client:
            yield client

    async def put_object(self, bucket: str, key: str, body: bytes, content_type: str) -> None:
        try:
            async with self._client() as client:
                await client.put_object(  # type: ignore[attr-defined]
                    Bucket=bucket, Key=key, Body=body, ContentType=content_type
                )
        except (ClientError, BotoCoreError) as e:
            raise _wrap(e, bucket=bucket, key=key) from e
        log.info("s3_put_object", bucket=bucket, key=key, size=len(body))

    async def get_object(self, bucket: str, key: str) -> bytes:
        try:
            async with self._client() as client:
                resp = await client.get_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
                async with resp["Body"] as stream:
                    data: bytes = await stream.read()
        except (ClientError, BotoCoreError) as e:
            raise _wrap(e, bucket=bucket, key=key) from e
        log.debug("s3_get_object", bucket=bucket, key=key, size=len(data))
        return data

    async def head_object(self, bucket: str, key: str) -> ObjectMetadata:
        try:
            async with self._client() as client:
                resp = await client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        except (ClientError, BotoCoreError) as e:
            raise _wrap(e, bucket=bucket, key=key) from e
        return ObjectMetadata(
            bucket=bucket,
            key=key,
            size=int(resp["ContentLength"]),
            etag=str(resp["ETag"]).strip('"'),
            last_modified=resp["LastModified"],
            content_type=resp.get("ContentType"),
        )

    async def head_bucket(self, bucket: str) -> None:
        """Fail loudly if the bucket is missing or unreadable. Used for startup checks."""
        try:
            async with self._client() as client:
                await client.head_bucket(Bucket=bucket)  # type: ignore[attr-defined]
        except (ClientError, BotoCoreError) as e:
            raise _wrap(e, bucket=bucket) from e


def build_s3_client() -> S3Client:
    return S3Client(get_settings().s3)
