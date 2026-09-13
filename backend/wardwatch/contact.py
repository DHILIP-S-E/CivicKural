"""KMS protection for notification routing data.

The raw WhatsApp destination exists only in memory while handling a provider
request. Persisted records contain AWS KMS ciphertext, never plaintext.
"""
from __future__ import annotations

import base64
import logging

import boto3

from .config import get_settings

logger = logging.getLogger(__name__)


def protect(value: str, tenant_id: str) -> str | None:
    settings = get_settings()
    if not value or not settings.contact_kms_key_id:
        if value and not settings.contact_kms_key_id:
            logger.warning(
                "contact.protect: contact_kms_key_id is not configured; "
                "citizen notification for tenant_id=%s will not be sent",
                tenant_id,
            )
        return None
    response = boto3.client("kms", region_name=settings.aws_region).encrypt(
        KeyId=settings.contact_kms_key_id,
        Plaintext=value.encode("utf-8"),
        EncryptionContext={"tenant_id": tenant_id, "purpose": "citizen-notification"},
    )
    return base64.b64encode(response["CiphertextBlob"]).decode("ascii")


def reveal(ciphertext: str, tenant_id: str) -> str:
    settings = get_settings()
    response = boto3.client("kms", region_name=settings.aws_region).decrypt(
        CiphertextBlob=base64.b64decode(ciphertext),
        EncryptionContext={"tenant_id": tenant_id, "purpose": "citizen-notification"},
    )
    return response["Plaintext"].decode("utf-8")
