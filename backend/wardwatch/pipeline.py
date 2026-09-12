"""Intake pipeline: 4-tier location pinning + intake -> dedup -> routing -> persist.

This is the deterministic glue the OrchestratorAgent drives (spec §1-§5).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from . import db, exif, geocode, storage
from .agents import dedup, routing
from .agents.intake import analyze
from .ids import hash_phone, new_complaint_id
from .models import (
    Complaint,
    Geo,
    GeoSource,
    Status,
    StatusEvent,
    TenantConfig,
)
from .sla import sla_deadline


@dataclass
class Submission:
    tenant_id: str
    ward_id: str
    citizen_phone: str
    photo: bytes | None
    transcript: str
    # WhatsApp native location share, if the citizen sent one.
    shared_location: tuple[float, float] | None = None
    # Optional free-text landmark, e.g. from the tier-4 clarification reply.
    landmark_text: str | None = None


@dataclass
class PipelineResult:
    kind: str  # "created" | "merged" | "needs_clarification" | "needs_location"
    complaint: Complaint | None = None
    message: str = ""


def pin_location(sub: Submission) -> Geo | None:
    if sub.shared_location:
        lat, lng = sub.shared_location
        return Geo(lat=lat, lng=lng, source=GeoSource.WHATSAPP_SHARE)

    if sub.photo:
        gps = exif.extract_gps(sub.photo)
        if gps:
            return Geo(lat=gps[0], lng=gps[1], source=GeoSource.EXIF)

    landmark = sub.landmark_text or sub.transcript
    if landmark:
        coords = geocode.geocode_landmark(sub.ward_id, landmark)
        if coords:
            src = GeoSource.DESCRIBED if sub.landmark_text else GeoSource.GEOCODED
            return Geo(lat=coords[0], lng=coords[1], source=src)

    return None


def run(sub: Submission, config: TenantConfig | None = None) -> PipelineResult:
    config = config or db.get_tenant_config(sub.tenant_id)

    geo = pin_location(sub)
    if geo is None:
        return PipelineResult(
            kind="needs_location",
            message="Please reply with the nearest street or landmark to the issue.",
        )

    intake = analyze(sub.photo, sub.transcript)
    if intake.needs_clarification:
        return PipelineResult(
            kind="needs_clarification",
            message=intake.clarification_question or "Could you clarify the issue?",
        )

    phone_hash = hash_phone(sub.citizen_phone)
    now = datetime.now(timezone.utc)

    # --- dedup ---
    open_same = db.open_complaints_by_category(
        sub.tenant_id, sub.ward_id, intake.category.value
    )
    decision = dedup.find_duplicate(geo, open_same)
    if decision.is_duplicate and decision.match:
        match = decision.match
        match.duplicate_reports_count += 1
        match.status_history.append(
            StatusEvent(
                status=match.status,
                ts=now,
                note=f"duplicate report merged (phone {phone_hash[:8]}, "
                f"{decision.distance_m:.0f}m away)",
            )
        )
        if decision.needs_review:
            match.needs_dedup_review = True
        db.put_complaint(match)
        return PipelineResult(
            kind="merged",
            complaint=match,
            message=f"This is already tracked as #{match.complaint_id}.",
        )

    # --- routing ---
    dept = routing.route(intake.category, intake.description, config)

    # --- persist ---
    cid = new_complaint_id(now)
    photo_key = None
    if sub.photo:
        photo_key = storage.photo_key(sub.tenant_id, cid, "before")
        storage.put_photo(photo_key, sub.photo)

    complaint = Complaint(
        complaint_id=cid,
        tenant_id=sub.tenant_id,
        ward_id=sub.ward_id,
        citizen_phone_hash=phone_hash,
        category=intake.category,
        severity=intake.severity,
        geo=geo,
        description=intake.description,
        language=intake.language,
        photo_s3_key=photo_key,
        status=Status.OPEN,
        created_at=now,
        sla_deadline=sla_deadline(intake.category, now, config),
        routed_dept=dept,
        status_history=[StatusEvent(status=Status.OPEN, ts=now)],
    )
    db.put_complaint(complaint)
    return PipelineResult(
        kind="created",
        complaint=complaint,
        message=f"Logged as #{cid}. Routed to {dept.value}. "
        f"Target resolution by {complaint.sla_deadline:%d %b %Y}.",
    )
