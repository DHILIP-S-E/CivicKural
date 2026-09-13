"""Opaque citizen access and community-reference tokens.

Complaint IDs are intentionally not authentication credentials.  Web reporters
receive a high-entropy token and only its digest is stored.  Community references
are signed, opaque handles that let the public support a nearby aggregate without
revealing the underlying complaint identifier or coordinates.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from .config import get_settings


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, digests: list[str]) -> bool:
    candidate = token_digest(token)
    return any(hmac.compare_digest(candidate, digest) for digest in digests)


def community_ref(tenant_id: str, ward_id: str, complaint_id: str) -> str:
    payload = f"{tenant_id}|{ward_id}|{complaint_id}"
    signature = hmac.new(
        get_settings().jwt_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:24]
    return f"{payload}|{signature}".encode("utf-8").hex()


def parse_community_ref(value: str) -> tuple[str, str, str] | None:
    try:
        decoded = bytes.fromhex(value).decode("utf-8")
        tenant_id, ward_id, complaint_id, signature = decoded.split("|", 3)
    except (ValueError, UnicodeDecodeError):
        return None
    expected = community_ref(tenant_id, ward_id, complaint_id)
    if not hmac.compare_digest(expected, value):
        return None
    return tenant_id, ward_id, complaint_id
