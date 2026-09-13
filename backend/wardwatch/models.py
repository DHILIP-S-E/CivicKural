"""Core domain models for WardWatch (spec §7)."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(str, enum.Enum):
    POTHOLE = "pothole"
    GARBAGE = "garbage"
    WATER_LEAK = "water_leak"
    STREETLIGHT = "streetlight"
    OTHER = "other"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthorityStatus(str, enum.Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    EVIDENCE_REQUESTED = "evidence_requested"
    RESOLVED = "resolved"


class Status(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    RESOLVED = "resolved"


class GeoSource(str, enum.Enum):
    WHATSAPP_SHARE = "whatsapp_share"
    EXIF = "exif"
    GEOCODED = "geocoded"
    DESCRIBED = "described"


class Dept(str, enum.Enum):
    ROADS = "roads"
    SANITATION = "sanitation"
    WATER_BOARD = "water_board"
    ELECTRICAL = "electrical"
    UNASSIGNED = "unassigned"


# Statuses that keep a complaint inside the SLA / escalation sweep.
OPEN_STATUSES = {Status.OPEN, Status.IN_PROGRESS, Status.PENDING_VERIFICATION}


class Geo(BaseModel):
    lat: float
    lng: float
    source: GeoSource


class StatusEvent(BaseModel):
    status: Status
    ts: datetime = Field(default_factory=utcnow)
    note: str | None = None
    source: str = "system"


class NotifyOutcome(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"


class NotifyAttempt(BaseModel):
    """Per-(complaint, escalation tier) citizen-notify delivery record (spec §7).

    Lets the escalation sweep skip re-sending a citizen update it already
    delivered successfully for a tier, and gives /admin/health something to
    count recent delivery failures from.
    """

    tier: int
    outcome: NotifyOutcome
    ts: datetime = Field(default_factory=utcnow)
    detail: str | None = None


class IntakeResult(BaseModel):
    """Structured JSON returned by IntakeAgent (spec §2)."""

    category: Category
    severity: Severity
    description: str
    language: str = "en"
    needs_clarification: bool = False
    clarification_question: str | None = None
    evidence_relevant: bool | None = None
    evidence_note: str | None = None
    issue_type: str | None = None


class Complaint(BaseModel):
    complaint_id: str
    tenant_id: str
    ward_id: str
    citizen_phone_hash: str
    category: Category
    issue_type: str = "other"
    severity: Severity
    priority: Priority = Priority.MEDIUM
    priority_factors: dict[str, int] = Field(default_factory=dict)
    geo: Geo
    description: str
    language: str = "en"
    photo_s3_key: str | None = None
    verification_photo_s3_key: str | None = None
    video_s3_key: str | None = None
    supporting_evidence_keys: list[str] = Field(default_factory=list)
    evidence_relevant: bool | None = None
    evidence_note: str | None = None
    status: Status = Status.OPEN
    # Set when a citizen rejects an officer's resolution via
    # /public/complaints/{id}/verify-resolution. We use a boolean flag rather than a
    # new Status value: escalation.py and sla.py branch on OPEN_STATUSES / Status
    # membership, and reverting to IN_PROGRESS on dispute already re-enters the SLA/
    # escalation sweep correctly without either module needing to know about disputes.
    citizen_disputed: bool = False
    # Web citizens receive a random bearer token. Only its SHA-256 digest is
    # persisted, so possession of a complaint ID alone never grants access.
    citizen_access_hashes: list[str] = Field(default_factory=list)
    # KMS ciphertexts only. Raw phone numbers are never persisted.
    citizen_contact_ciphertexts: list[str] = Field(default_factory=list)
    # Delivery channel per entry above, index-aligned with
    # citizen_contact_ciphertexts ("whatsapp" | "sms" | "email"). Missing/short
    # relative to citizen_contact_ciphertexts (records written before this field
    # existed) defaults to "whatsapp" at the send site.
    citizen_contact_channels: list[str] = Field(default_factory=list)
    duplicate_of: str | None = None
    duplicate_reports_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    sla_deadline: datetime
    routed_dept: Dept = Dept.UNASSIGNED
    authority_status: AuthorityStatus = AuthorityStatus.NOT_SUBMITTED
    authority_ticket_id: str | None = None
    escalation_count: int = 0
    escalation_tier: int = 0
    needs_dedup_review: bool = False
    resolved_at: datetime | None = None
    verification_confidence: str | None = None
    verification_reason: str | None = None
    citizen_updates: list[str] = Field(default_factory=list)
    status_history: list[StatusEvent] = Field(default_factory=list)
    citizen_notify_log: list[NotifyAttempt] = Field(default_factory=list)

    @property
    def pk(self) -> str:
        return f"{self.tenant_id}#{self.ward_id}"


class InfraFlag(BaseModel):
    """Pattern-agent finding (spec §9) — not a complaint."""

    flag_id: str
    tenant_id: str
    ward_id: str
    category: Category
    centroid: Geo
    incident_count: int
    window_days: int
    summary: str
    created_at: datetime = Field(default_factory=utcnow)


class TenantConfig(BaseModel):
    tenant_id: str
    sla_overrides: dict[str, int] = Field(default_factory=dict)  # category -> days
    routing_overrides: dict[str, str] = Field(default_factory=dict)  # category -> dept
    dept_contacts: dict[str, str] = Field(default_factory=dict)  # dept -> email/phone
    priority_weights: dict[str, int] = Field(default_factory=dict)

    @field_validator("sla_overrides")
    @classmethod
    def valid_sla_overrides(cls, value: dict[str, int]) -> dict[str, int]:
        for category, days in value.items():
            Category(category)
            if not 1 <= int(days) <= 365:
                raise ValueError("SLA days must be between 1 and 365")
        return value
    @field_validator("routing_overrides")
    @classmethod
    def valid_routing_overrides(cls, value: dict[str, str]) -> dict[str, str]:
        for category, department in value.items():
            Category(category)
            Dept(department)
        return value

    @field_validator("priority_weights")
    @classmethod
    def valid_priority_weights(cls, value: dict[str, int]) -> dict[str, int]:
        allowed = {
            "severity", "safety", "sensitive_location", "community_reports",
            "duration", "people_affected", "evidence",
        }
        for factor, weight in value.items():
            if factor not in allowed or not 0 <= int(weight) <= 10:
                raise ValueError("priority weights must use known factors and values from 0 to 10")
        return value


class InboundSession(BaseModel):
    tenant_id: str
    ward_id: str
    citizen_phone_hash: str
    transcript: str = ""
    photo_s3_key: str | None = None
    shared_location: tuple[float, float] | None = None
    landmark_text: str | None = None
    language: str = "en"
    awaiting_location: bool = False
    expires_at: int


class OtpChallenge(BaseModel):
    """Short-lived phone-verification OTP challenge (DynamoDB TTL item).

    Only the SHA-256 digest of the 6-digit code is ever persisted — never the
    plaintext code, and never the plaintext phone number (phone_hash mirrors
    Complaint.citizen_phone_hash, the only identifier we store)."""

    tenant_id: str
    phone_hash: str
    code_hash: str
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: int


class PhoneSession(BaseModel):
    """Login session issued after a successful OTP confirm, used both for the
    "my reports" lookup and to authenticate web report submission.

    Only the SHA-256 digest of the opaque bearer token is persisted. The
    phone number itself is stored only as KMS ciphertext (phone_ciphertext),
    never in plaintext, mirroring citizen_contact_ciphertexts on Complaint."""

    tenant_id: str
    phone_hash: str
    token_digest: str
    phone_ciphertext: str
    expires_at: int
