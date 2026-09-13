"""Phone-OTP verification + "my reports" session tokens.

Mirrors citizen_access.py's token pattern: an opaque, high-entropy bearer
token is handed to the citizen and only its SHA-256 digest is persisted.
OTP codes follow the same rule — only a SHA-256 digest of the 6-digit code
is ever stored, never the plaintext code, and never the plaintext phone
number (only Complaint.citizen_phone_hash-style hashes are persisted)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from . import db
from . import contact
from .models import OtpChallenge, PhoneSession

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
# Citizen login session TTL. This session now doubles as the login required to
# submit a web report (not just "my reports" lookup), so it is long-lived like
# a normal login rather than a short OTP-confirmation window.
PHONE_SESSION_TTL_DAYS = 30
# Distinct KMS encryption-context purpose from contact.py's "citizen-notification"
# ciphertexts — this ciphertext is never used to send a notification, only to
# recover the citizen's phone number for an authenticated session.
PHONE_SESSION_KMS_PURPOSE = "citizen-session"


def new_otp_code() -> str:
    """6-digit numeric code using a CSPRNG (never `random`)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _code_digest(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def resend_blocked(existing: OtpChallenge | None, now: datetime | None = None) -> bool:
    """True if an unexpired challenge was created within the resend cooldown."""
    if existing is None:
        return False
    now = now or datetime.now(timezone.utc)
    created_at = existing.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS


def request_otp(tenant_id: str, phone_hash: str) -> str:
    """Create/overwrite an OTP challenge and return the plaintext code to send.

    Caller is responsible for checking `resend_blocked` first."""
    code = new_otp_code()
    now = datetime.now(timezone.utc)
    challenge = OtpChallenge(
        tenant_id=tenant_id,
        phone_hash=phone_hash,
        code_hash=_code_digest(code),
        attempts=0,
        created_at=now,
        expires_at=int((now + timedelta(minutes=OTP_TTL_MINUTES)).timestamp()),
    )
    db.create_otp_challenge(challenge)
    return code


def confirm_otp(tenant_id: str, phone_hash: str, code: str) -> bool:
    """Validate `code` against the stored challenge. On success the challenge is
    deleted. On failure, attempts are incremented (and the challenge deleted once
    the attempt cap is hit) and False is returned."""
    challenge = db.get_otp_challenge(tenant_id, phone_hash)
    if challenge is None:
        return False

    now = datetime.now(timezone.utc)
    if challenge.expires_at <= int(now.timestamp()):
        db.delete_otp_challenge(tenant_id, phone_hash)
        return False
    if challenge.attempts >= OTP_MAX_ATTEMPTS:
        db.delete_otp_challenge(tenant_id, phone_hash)
        return False

    if not hmac.compare_digest(_code_digest(code), challenge.code_hash):
        db.increment_otp_attempts(tenant_id, phone_hash)
        if challenge.attempts + 1 >= OTP_MAX_ATTEMPTS:
            db.delete_otp_challenge(tenant_id, phone_hash)
        return False

    db.delete_otp_challenge(tenant_id, phone_hash)
    return True


def issue_phone_session(tenant_id: str, phone_hash: str, phone: str) -> str:
    """Create a new phone session and return the plaintext bearer token.

    `phone` is the verified plaintext phone number; it is protected with KMS
    (never stored in plaintext) so a later verified request can recover it,
    e.g. to attribute a web report to the logged-in citizen."""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    phone_ciphertext = contact.protect(phone, tenant_id, purpose=PHONE_SESSION_KMS_PURPOSE)
    session = PhoneSession(
        tenant_id=tenant_id,
        phone_hash=phone_hash,
        token_digest=digest,
        phone_ciphertext=phone_ciphertext or "",
        expires_at=int((now + timedelta(days=PHONE_SESSION_TTL_DAYS)).timestamp()),
    )
    db.create_phone_session(session)
    return token


def verify_phone_session(tenant_id: str, token: str) -> str | None:
    """Return the phone_hash for a valid, unexpired session token, else None."""
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.get_phone_session(digest)
    if session is None:
        return None
    if not hmac.compare_digest(session.token_digest, digest):
        return None
    if session.tenant_id != tenant_id:
        return None
    now = int(datetime.now(timezone.utc).timestamp())
    if session.expires_at <= now:
        return None
    return session.phone_hash


def resolve_session_phone(tenant_id: str, token: str) -> str | None:
    """Return the verified plaintext phone number for a valid, unexpired
    session token, else None. Used to attribute an authenticated action (e.g.
    a web report submission) to the logged-in citizen's real phone number."""
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.get_phone_session(digest)
    if session is None:
        return None
    if not hmac.compare_digest(session.token_digest, digest):
        return None
    if session.tenant_id != tenant_id:
        return None
    now = int(datetime.now(timezone.utc).timestamp())
    if session.expires_at <= now:
        return None
    if not session.phone_ciphertext:
        return None
    return contact.reveal(session.phone_ciphertext, tenant_id, purpose=PHONE_SESSION_KMS_PURPOSE)
