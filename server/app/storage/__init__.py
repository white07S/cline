"""Object storage layer.

The S3 wrapper is the only entry point — never call boto3 / aioboto3 directly
from feature code. Domain errors live in `errors.py` and wrap the underlying
botocore exceptions so callers don't have to import botocore.
"""

from app.storage.s3 import (
    ObjectMetadata,
    S3Client,
    S3Error,
    build_s3_client,
)

__all__ = [
    "ObjectMetadata",
    "S3Client",
    "S3Error",
    "build_s3_client",
]
