"""Public accountability routes — no login, aggregates only (spec §5, §10).

Also hosts the citizen-facing web report intake (spec §0-§5) and the community
upvote / support flow — both citizen-authenticated by nothing (public, rate-limit
worth adding later; there is no existing rate-limit infra in this repo to reuse,
so it is intentionally skipped here).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import base64

from pydantic import BaseModel

from .. import aggregates, db, geo, storage, transcribe
from ..config import get_settings
from ..models import Status, StatusEvent
from ..pipeline import PipelineResult, Submission, run
from ..wards import wards_for

router = APIRouter(prefix="/public", tags=["public"])

# Statuses at which a citizen can weigh in on a claimed resolution.
_VERIFIABLE_STATUSES = {Status.RESOLVED, Status.PENDING_VERIFICATION}


def _all_complaints(tenant_id: str):
    return db.query_tenant_complaints(tenant_id, wards_for(tenant_id))


@router.get("/compliance")
def compliance(tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    complaints = _all_complaints(tid)
    return {
        "tenant_id": tid,
        "departments": aggregates.dept_sla_compliance(complaints),
        "totals": aggregates.status_totals(complaints),
    }


@router.get("/dashboard")
def dashboard(tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    complaints = _all_complaints(tid)
    totals = aggregates.status_totals(complaints)
    cat_totals = aggregates.category_totals(complaints)
    top_categories = sorted(cat_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "tenant_id": tid,
        "total": sum(totals.values()),
        "status_totals": totals,
        "resolution_rate": aggregates.resolution_rate(totals),
        "top_categories": [{"category": k, "count": v} for k, v in top_categories],
    }


@router.get("/hotspots")
def hotspots(tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    return {"tenant_id": tid, "bins": aggregates.hotspot_density(_all_complaints(tid))}


@router.post("/reports")
async def submit_report(
    transcript: str = Form(...),
    ward_id: str = Form(...),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    tenant_id: str | None = Form(None),
    photo: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    audio_format: str = Form("ogg"),
    video: UploadFile | None = File(None),
) -> dict:
    """Web-based citizen report intake — runs the same pipeline as the WhatsApp
    webhook, but bypasses the messenger reply path (there is no phone number to
    reply to for a web submission)."""
    tid = tenant_id or get_settings().default_tenant_id
    photo_bytes = await photo.read() if photo is not None else None
    shared_location = (lat, lng) if lat is not None and lng is not None else None

    full_transcript = transcript
    if audio is not None:
        audio_bytes = await audio.read()
        voice_text = transcribe.transcribe_audio(audio_bytes, audio_format)
        full_transcript = f"{transcript}\n{voice_text}".strip() if transcript else voice_text

    import secrets

    sub = Submission(
        tenant_id=tid,
        ward_id=ward_id,
        citizen_phone=f"web-{secrets.token_hex(8)}",
        photo=photo_bytes,
        transcript=full_transcript,
        shared_location=shared_location,
    )
    result: PipelineResult = run(sub)

    if result.kind in ("created", "merged"):
        if video is not None and result.complaint is not None:
            video_bytes = await video.read()
            ext = (video.filename or "video.mp4").rsplit(".", 1)[-1] or "mp4"
            key = storage.photo_key(tid, result.complaint.complaint_id, "video", ext=ext)
            storage.put_photo(key, video_bytes, content_type=video.content_type or "video/mp4")
            result.complaint.video_s3_key = key
            db.put_complaint(result.complaint)
        return {
            "status": "created",
            "complaint_id": result.complaint.complaint_id if result.complaint else None,
            "kind": result.kind,
            "message": result.message,
        }
    return {"status": "needs_more_info", "message": result.message}


def _complaint_summary(c) -> dict:
    """Public-safe view of a complaint — no phone hash, no officer-only fields."""
    return {
        "id": c.complaint_id,
        "category": c.category.value,
        "severity": c.severity.value,
        "status": c.status.value,
        "created_at": c.created_at.isoformat(),
        "duplicate_reports_count": c.duplicate_reports_count,
        "lat": round(c.geo.lat, 3),
        "lng": round(c.geo.lng, 3),
    }


@router.get("/complaints/nearby")
def nearby_complaints(
    lat: float,
    lng: float,
    category: str | None = None,
    radius_m: float = 500,
    tenant_id: str | None = None,
) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    complaints = _all_complaints(tid)
    out = []
    for c in complaints:
        if category and c.category.value != category:
            continue
        d = geo.haversine_m(lat, lng, c.geo.lat, c.geo.lng)
        if d <= radius_m:
            out.append(_complaint_summary(c))
    return {"tenant_id": tid, "complaints": out}


def _find_complaint(tenant_id: str, complaint_id: str):
    for c in _all_complaints(tenant_id):
        if c.complaint_id == complaint_id:
            return c
    return None


@router.get("/complaints/{complaint_id}")
def complaint_detail(complaint_id: str, tenant_id: str | None = None) -> dict:
    """Public-safe complaint detail with before/after photo links (spec §5).

    No citizen_phone_hash or other officer-only fields. VerificationOutcome
    (confidence/reason) is not persisted anywhere on Complaint today — only the
    resulting Status and a free-text StatusEvent.note are stored — so those fields
    are omitted here rather than fabricated.
    """
    tid = tenant_id or get_settings().default_tenant_id
    c = _find_complaint(tid, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="complaint not found")
    out = _complaint_summary(c)
    out["citizen_disputed"] = c.citizen_disputed
    out["before_photo_url"] = storage.presigned_url(c.photo_s3_key) if c.photo_s3_key else None
    out["after_photo_url"] = (
        storage.presigned_url(c.verification_photo_s3_key) if c.verification_photo_s3_key else None
    )
    return out


class VerifyResolutionBody(BaseModel):
    confirmed: bool
    new_photo_b64: str | None = None


@router.post("/complaints/{complaint_id}/verify-resolution")
async def verify_resolution_by_citizen(complaint_id: str, body: VerifyResolutionBody, tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    c = _find_complaint(tid, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="complaint not found")
    if c.status not in _VERIFIABLE_STATUSES:
        raise HTTPException(status_code=400, detail="complaint is not awaiting resolution verification")

    now = datetime.now(timezone.utc)
    if body.confirmed:
        c.status_history.append(
            StatusEvent(status=c.status, ts=now, note="citizen confirmed resolution")
        )
    else:
        c.citizen_disputed = True
        c.status = Status.IN_PROGRESS
        c.status_history.append(
            StatusEvent(status=Status.IN_PROGRESS, ts=now, note="citizen disputed resolution")
        )
        if body.new_photo_b64:
            photo = base64.b64decode(body.new_photo_b64)
            key = storage.photo_key(c.tenant_id, c.complaint_id, "dispute")
            storage.put_photo(key, photo)
            c.verification_photo_s3_key = key
    db.put_complaint(c)
    return {"status": "ok", "complaint": _complaint_summary(c) | {"citizen_disputed": c.citizen_disputed}}


@router.post("/complaints/{complaint_id}/support")
async def support_complaint(
    complaint_id: str,
    ward_id: str = Form(...),
    tenant_id: str | None = Form(None),
    photo: UploadFile | None = File(None),
) -> dict:
    """Community 'this is happening to me too' — bumps duplicate_reports_count and
    appends a StatusEvent, mirroring the dedup-merge path in pipeline.run()."""
    tid = tenant_id or get_settings().default_tenant_id
    complaint = db.get_complaint(tid, ward_id, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="complaint not found")

    if photo is not None:
        await photo.read()  # accepted for future evidence storage, not persisted yet

    now = datetime.now(timezone.utc)
    complaint.duplicate_reports_count += 1
    complaint.status_history.append(
        StatusEvent(status=complaint.status, ts=now, note="community support: +1 report")
    )
    db.put_complaint(complaint)
    return {"status": "ok", "complaint": _complaint_summary(complaint)}
