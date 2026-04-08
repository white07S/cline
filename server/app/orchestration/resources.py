"""Typed Dagster resources.

Resources are how Dagster code accesses external systems. We expose ours as
`ConfigurableResource` subclasses so the schema is checked at load time and
the IDE/mypy can see the types.
"""

from __future__ import annotations

from dagster import ConfigurableResource

from app.storage.s3 import S3Client, build_s3_client


class S3Resource(ConfigurableResource):
    """Wraps the app's S3Client so assets can `s3: S3Resource` and call methods on it.

    Holds no config of its own — all S3 configuration lives in the Pydantic
    `Settings` model and is read from `configs/s3.yml` + env vars. Keeping the
    config in one place avoids drift between FastAPI code and Dagster code.
    """

    def get_client(self) -> S3Client:
        return build_s3_client()
