"""Hello-world asset that proves the wiring works end-to-end.

It writes a small marker object to the `documents` bucket in MinIO using the
typed S3Resource. Replace this with real ingestion assets as the platform grows.

Note: this module deliberately does NOT use `from __future__ import annotations`.
Dagster's `@asset` decorator inspects the runtime annotation of `context` to
validate it; with PEP 563 string annotations the check sees a `str` and
rejects it.
"""

from datetime import UTC, datetime

from dagster import AssetExecutionContext, asset

from app.orchestration.resources import S3Resource
from app.settings import get_settings


@asset(group_name="bootstrap", compute_kind="python")
async def hello_marker(context: AssetExecutionContext, s3: S3Resource) -> str:
    """Drop a small timestamped marker into MinIO.

    Returns the object key so downstream assets can depend on it.
    """
    settings = get_settings()
    bucket = settings.s3.buckets.documents
    key = f"bootstrap/hello-{datetime.now(tz=UTC).isoformat()}.txt"
    body = b"hello from dagster\n"

    client = s3.get_client()
    await client.put_object(bucket=bucket, key=key, body=body, content_type="text/plain")

    context.log.info(f"wrote marker to s3://{bucket}/{key}")
    return key
