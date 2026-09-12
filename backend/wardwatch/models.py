"""Core domain models for WardWatch (spec §7)."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


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


class IntakeResult(BaseModel):
    """Structured JSON returned by IntakeAgent (spec §2)."""

    category: Category
    severity: Severity
    description: str
    language: str = "en"
    needs_clarification: bool = False
    clarification_question: str | None = None


class Complaint(BaseModel):
    complaint_id: str
    tenant_id: str
    ward_id: str
    citizen_phone_hash: str
    category: Category
    severity: Severity
    geo: Geo
    description: str
    language: str = "en"
    photo_s3_key: str | None = None
    verification_photo_s3_key: str | None = None
    video_s3_key: str | None = None
    status: Status = Status.OPEN
    # Set when a citizen rejects an officer's resolution via
    # /public/complaints/{id}/verify-resolution. We use a boolean flag rather than a
    # new Status value: escalation.py and sla.py branch on OPEN_STATUSES / Status
    # membership, and reverting to IN_PROGRESS on dispute already re-enters the SLA/
    # escalation sweep correctly without either module needing to know about disputes.
    citizen_disputed: bool = False
    duplicate_of: str | None = None
    duplicate_reports_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    sla_deadline: datetime
    routed_dept: Dept = Dept.UNASSIGNED
    escalation_count: int = 0
    escalation_tier: int = 0
    needs_dedup_review: bool = False
    status_history: list[StatusEvent] = Field(default_factory=list)

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
