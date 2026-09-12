"""S3 storage for before/after photos (spec §5, §8)."""
from __future__ import annotations

from datetime import datetime, timezone

import boto3

from .config import get_settings


def _client():
    return boto3.client("s3", region_name=get_settings().aws_region)


def photo_key(tenant_id: str, complaint_id: str, kind: str = "before", ext: str = "jpg") -> str:
    now = datetime.now(timezone.utc)
    slug = complaint_id.lower().replace("wm-", "wm-")
    return f"{tenant_id}/{now:%Y/%m}/{slug}-{kind}.{ext}"


def put_photo(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    _client().put_object(
        Bucket=get_settings().wardwatch_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def get_photo(key: str) -> bytes:
    resp = _client().get_object(Bucket=get_settings().wardwatch_bucket, Key=key)
    return resp["Body"].read()


def presigned_url(key: str, expires: int = 900) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": get_settings().wardwatch_bucket, "Key": key},
        ExpiresIn=expires,
    )
