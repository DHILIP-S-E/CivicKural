"""Deterministic-ish ID + phone-hash helpers."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone


def hash_phone(phone: str) -> str:
    """SHA-256 of the citizen phone — the ONLY identifier we store (spec §4)."""
    normalized = phone.strip().replace(" ", "").replace("-", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def new_complaint_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"WM-{now:%Y}-{secrets.randbelow(1_000_000):06d}"


def new_flag_id() -> str:
    return secrets.token_hex(8)
