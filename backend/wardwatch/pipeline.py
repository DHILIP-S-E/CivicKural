"""Intake pipeline: 4-tier location pinning + intake -> dedup -> routing -> persist.

This is the deterministic glue the OrchestratorAgent drives (spec §1-§5).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from . import db, exif, geocode, storage
from .agents import dedup, routing
from .agents.intake import analyze
from .citizen_access import new_access_token, token_digest
from .contact import protect
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
from .priority import assess
from .localize import detect_language, message as citizen_message


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
    issue_citizen_token: bool = False
    # Optional SMS contact for citizens without a WhatsApp thread (e.g. the web
    # intake form). When set, this — not citizen_phone — is protected as the
    # citizen's notification destination, tagged with the "sms" channel so
    # escalation notifications route through SNS instead of WhatsApp.
    contact_phone: str | None = None


@dataclass
class PipelineResult:
    kind: str  # "created" | "merged" | "needs_clarification" | "needs_location"
    complaint: Complaint | None = None
    message: str = ""
    citizen_access_token: str | None = None


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
        language = detect_language(sub.transcript or sub.landmark_text or "")
        return PipelineResult(
            kind="needs_location",
            message=citizen_message(language, "needs_location"),
        )

    intake = analyze(sub.photo, sub.transcript)
    if intake.needs_clarification:
        return PipelineResult(
            kind="needs_clarification",
            message=intake.clarification_question or "Could you clarify the issue?",
        )
    if sub.photo and intake.evidence_relevant is False:
        return PipelineResult(
            kind="needs_clarification",
            message=intake.evidence_note or "Please upload a clearer photo showing the reported issue.",
        )

    phone_hash = hash_phone(sub.citizen_phone)
    now = datetime.now(timezone.utc)
    contact_value = sub.contact_phone or sub.citizen_phone
    contact_channel = "sms" if sub.contact_phone else "whatsapp"

    # --- dedup ---
    open_same = db.open_complaints_by_category(
        sub.tenant_id, sub.ward_id, intake.category.value
    )
    decision = dedup.find_duplicate(geo, open_same)
    if decision.is_duplicate and decision.match:
        match = decision.match
        access_token = new_access_token() if sub.issue_citizen_token else None
        if access_token:
            match.citizen_access_hashes.append(token_digest(access_token))
        protected = protect(contact_value, sub.tenant_id)
        if protected:
            match.citizen_contact_ciphertexts.append(protected)
            match.citizen_contact_channels.append(contact_channel)
        match.duplicate_reports_count += 1
        priority = assess(
            match.category, match.severity, match.description,
            match.duplicate_reports_count + 1, config,
            match.evidence_relevant,
        )
        match.priority = priority.priority
        match.priority_factors = priority.factors | {"score": priority.score}
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
            message=citizen_message(intake.language, "merged", id=match.complaint_id),
            citizen_access_token=access_token,
        )

    # --- routing ---
    dept = routing.route(intake.category, intake.description, config)
    priority = assess(
        intake.category, intake.severity, intake.description, 1, config, intake.evidence_relevant
    )
    access_token = new_access_token() if sub.issue_citizen_token else None
    protected = protect(contact_value, sub.tenant_id)

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
        issue_type=intake.issue_type or intake.category.value,
        severity=intake.severity,
        priority=priority.priority,
        priority_factors=priority.factors | {"score": priority.score},
        geo=geo,
        description=intake.description,
        language=intake.language,
        photo_s3_key=photo_key,
        status=Status.OPEN,
        created_at=now,
        sla_deadline=sla_deadline(intake.category, now, config),
        routed_dept=dept,
        citizen_access_hashes=[token_digest(access_token)] if access_token else [],
        citizen_contact_ciphertexts=[protected] if protected else [],
        citizen_contact_channels=[contact_channel] if protected else [],
        evidence_relevant=intake.evidence_relevant,
        evidence_note=intake.evidence_note,
        status_history=[StatusEvent(status=Status.OPEN, ts=now)],
    )
    db.put_complaint(complaint)
    return PipelineResult(
        kind="created",
        complaint=complaint,
        message=citizen_message(
            intake.language,
            "created",
            id=cid,
            dept=dept.value,
            date=f"{complaint.sla_deadline:%d %b %Y}",
        ),
        citizen_access_token=access_token,
    )
