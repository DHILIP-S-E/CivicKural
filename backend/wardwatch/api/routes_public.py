"""Public accountability routes — no login, aggregates only (spec §5, §10).

Also hosts the citizen-facing web report intake and privacy-safe community
support flow. Deployment-level throttling is defined in the HTTP API template.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

import base64
import binascii
import re

from pydantic import BaseModel, field_validator

from .. import aggregates, db, geo, notify, storage, transcribe
from ..citizen_access import community_ref, parse_community_ref, token_matches
from ..config import get_settings
from ..ids import hash_phone
from ..models import Status, StatusEvent
from ..phone_session import (
    confirm_otp,
    issue_phone_session,
    request_otp,
    resend_blocked,
    resolve_session_phone,
    verify_phone_session,
)
from ..pipeline import PipelineResult, Submission, run
from ..priority import assess
from ..wards import wards_for

router = APIRouter(prefix="/public", tags=["public"])
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024

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
        "success_metrics": aggregates.success_metrics(complaints),
    }


@router.get("/hotspots")
def hotspots(tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    return {"tenant_id": tid, "bins": aggregates.hotspot_density(_all_complaints(tid))}


@router.get("/community-priorities")
def community_priorities(tenant_id: str | None = None) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    return {"tenant_id": tid, "issues": aggregates.community_priorities(_all_complaints(tid))}


@router.post("/reports")
async def submit_report(
    transcript: str = Form(""),
    ward_id: str = Form(...),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    tenant_id: str | None = Form(None),
    photo: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    audio_format: str = Form("ogg"),
    video: UploadFile | None = File(None),
    x_phone_session: str = Header(default=""),
) -> dict:
    """Web-based citizen report intake — runs the same pipeline as the WhatsApp
    webhook, but bypasses the messenger reply path (there is no phone number to
    reply to for a web submission). Requires a verified phone-OTP login session
    (X-Phone-Session header) so every web report is attributable to a real,
    verified phone number — the same one used for SMS status/escalation
    updates and for the "my reports" lookup."""
    tid = tenant_id or get_settings().default_tenant_id
    phone = resolve_session_phone(tid, x_phone_session)
    if phone is None:
        raise HTTPException(status_code=401, detail="phone session required")
    if ward_id not in wards_for(tid):
        raise HTTPException(status_code=400, detail="invalid ward for tenant")
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=400, detail="latitude and longitude must be supplied together")
    if lat is not None and lng is not None and not geo.in_ward_bbox(ward_id, lat, lng):
        raise HTTPException(status_code=400, detail="location is outside the selected ward")
    photo_bytes = await photo.read() if photo is not None else None
    if photo_bytes is not None and len(photo_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="photo exceeds 10 MB")
    shared_location = (lat, lng) if lat is not None and lng is not None else None

    full_transcript = transcript
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="audio exceeds 20 MB")
        voice_text = transcribe.transcribe_audio(audio_bytes, audio_format)
        full_transcript = f"{transcript}\n{voice_text}".strip() if transcript else voice_text

    sub = Submission(
        tenant_id=tid,
        ward_id=ward_id,
        citizen_phone=phone,
        photo=photo_bytes,
        transcript=full_transcript,
        shared_location=shared_location,
        issue_citizen_token=True,
    )
    if not full_transcript.strip() and photo_bytes is None:
        raise HTTPException(status_code=400, detail="provide a description, voice note, or photo")
    result: PipelineResult = run(sub)

    if result.kind in ("created", "merged"):
        if video is not None and result.complaint is not None:
            video_bytes = await video.read()
            if len(video_bytes) > MAX_VIDEO_BYTES:
                raise HTTPException(status_code=413, detail="video exceeds 50 MB")
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
            "citizen_access_token": result.citizen_access_token,
        }
    return {"status": "needs_more_info", "message": result.message}


def _complaint_summary(c) -> dict:
    """Citizen-owned view; callers are authenticated by a per-report token."""
    return {
        "id": c.complaint_id,
        "category": c.category.value,
        "issue_type": c.issue_type,
        "severity": c.severity.value,
        "status": c.status.value,
        "created_at": c.created_at.isoformat(),
        "duplicate_reports_count": c.duplicate_reports_count,
        "priority": c.priority.value,
        "authority_status": c.authority_status.value,
        "authority_ticket_id": c.authority_ticket_id,
        "updates": c.citizen_updates,
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
            # Opaque community handle; no complaint ID, coordinates, photos, or
            # transcript are disclosed by this public discovery endpoint.
            out.append({
                "community_ref": community_ref(tid, c.ward_id, c.complaint_id),
                "category": c.category.value,
                "priority": c.priority.value,
                "status": c.status.value,
                "report_count": c.duplicate_reports_count + 1,
            })
    return {"tenant_id": tid, "community_issues": out}


def _find_complaint(tenant_id: str, complaint_id: str):
    for c in _all_complaints(tenant_id):
        if c.complaint_id == complaint_id:
            return c
    return None


@router.get("/complaints/{complaint_id}")
def complaint_detail(
    complaint_id: str,
    tenant_id: str | None = None,
    x_citizen_token: str = Header(default=""),
) -> dict:
    """Private citizen-owned detail, protected by the report access token."""
    tid = tenant_id or get_settings().default_tenant_id
    c = _find_complaint(tid, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="complaint not found")
    if not token_matches(x_citizen_token, c.citizen_access_hashes):
        raise HTTPException(status_code=403, detail="citizen access token required")
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
async def verify_resolution_by_citizen(
    complaint_id: str,
    body: VerifyResolutionBody,
    tenant_id: str | None = None,
    x_citizen_token: str = Header(default=""),
) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    c = _find_complaint(tid, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="complaint not found")
    if not token_matches(x_citizen_token, c.citizen_access_hashes):
        raise HTTPException(status_code=403, detail="citizen access token required")
    if c.status not in _VERIFIABLE_STATUSES:
        raise HTTPException(status_code=400, detail="complaint is not awaiting resolution verification")

    now = datetime.now(timezone.utc)
    if body.confirmed:
        c.citizen_disputed = False
        c.status_history.append(
            StatusEvent(status=c.status, ts=now, note="citizen confirmed resolution", source="citizen")
        )
    else:
        c.citizen_disputed = True
        c.status = Status.IN_PROGRESS
        c.status_history.append(
            StatusEvent(status=Status.IN_PROGRESS, ts=now, note="citizen disputed resolution", source="citizen")
        )
        if body.new_photo_b64:
            try:
                photo = base64.b64decode(body.new_photo_b64, validate=True)
            except (binascii.Error, ValueError):
                raise HTTPException(status_code=400, detail="invalid photo encoding")
            if not photo or len(photo) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="photo must be between 1 byte and 10 MB")
            key = storage.photo_key(c.tenant_id, c.complaint_id, "dispute")
            storage.put_photo(key, photo)
            c.verification_photo_s3_key = key
    db.put_complaint(c)
    return {"status": "ok", "complaint": _complaint_summary(c) | {"citizen_disputed": c.citizen_disputed}}


@router.post("/community/{reference}/support")
async def support_complaint(
    reference: str,
    photo: UploadFile | None = File(None),
) -> dict:
    """Community 'this is happening to me too' — bumps duplicate_reports_count and
    appends a StatusEvent, mirroring the dedup-merge path in pipeline.run()."""
    parsed = parse_community_ref(reference)
    if parsed is None:
        raise HTTPException(status_code=404, detail="community issue not found")
    tid, ward_id, complaint_id = parsed
    complaint = db.get_complaint(tid, ward_id, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="complaint not found")

    if photo is not None:
        evidence = await photo.read()
        if len(evidence) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="photo exceeds 10 MB")
        ext = (photo.filename or "evidence.jpg").rsplit(".", 1)[-1] or "jpg"
        key = storage.photo_key(tid, complaint_id, f"support-{complaint.duplicate_reports_count + 1}", ext)
        storage.put_photo(key, evidence, content_type=photo.content_type or "image/jpeg")
        complaint.supporting_evidence_keys.append(key)

    now = datetime.now(timezone.utc)
    complaint.duplicate_reports_count += 1
    priority = assess(
        complaint.category,
        complaint.severity,
        complaint.description,
        complaint.duplicate_reports_count + 1,
        db.get_tenant_config(tid),
        complaint.evidence_relevant,
    )
    complaint.priority = priority.priority
    complaint.priority_factors = priority.factors | {"score": priority.score}
    complaint.status_history.append(
        StatusEvent(status=complaint.status, ts=now, note="community support: +1 report", source="community")
    )
    db.put_complaint(complaint)
    return {"status": "ok", "report_count": complaint.duplicate_reports_count + 1}


# --- Feature: citizen phone-OTP verification + "my reports" lookup ---

def _india_phone(value: str) -> str:
    """Accept Indian mobile numbers only and return canonical E.164 form."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("enter a valid 10-digit Indian mobile number")
    return f"+91{digits}"

class VerifyPhoneRequestBody(BaseModel):
    tenant_id: str
    phone: str

    _normalize_phone = field_validator("phone")(_india_phone)


class VerifyPhoneConfirmBody(BaseModel):
    tenant_id: str
    phone: str
    code: str

    _normalize_phone = field_validator("phone")(_india_phone)


@router.post("/verify-phone/request")
def verify_phone_request(body: VerifyPhoneRequestBody) -> dict:
    """Send a 6-digit WhatsApp OTP to `phone`. Always responds generically — the
    response never reveals whether the phone has any reports on file, to
    avoid enumeration."""
    phone_hash = hash_phone(body.phone)
    existing = db.get_otp_challenge(body.tenant_id, phone_hash)
    if resend_blocked(existing):
        raise HTTPException(status_code=429, detail="please wait before requesting another code")
    code = request_otp(body.tenant_id, phone_hash)
    try:
        notify.send_whatsapp_otp(body.phone, code)
    except notify.WhatsAppOtpUnavailable as exc:
        db.delete_otp_challenge(body.tenant_id, phone_hash)
        raise HTTPException(status_code=503, detail="WhatsApp OTP is not configured") from exc
    except Exception as exc:
        db.delete_otp_challenge(body.tenant_id, phone_hash)
        raise HTTPException(status_code=503, detail="WhatsApp could not send the verification code") from exc
    return {"sent": True}


@router.post("/verify-phone/confirm")
def verify_phone_confirm(body: VerifyPhoneConfirmBody) -> dict:
    phone_hash = hash_phone(body.phone)
    if not confirm_otp(body.tenant_id, phone_hash, body.code):
        raise HTTPException(status_code=400, detail="invalid or expired code")
    token = issue_phone_session(body.tenant_id, phone_hash, body.phone)
    return {"session_token": token}


@router.get("/my-reports")
def my_reports(
    tenant_id: str | None = None,
    x_phone_session: str = Header(default=""),
) -> dict:
    tid = tenant_id or get_settings().default_tenant_id
    phone_hash = verify_phone_session(tid, x_phone_session)
    if phone_hash is None:
        raise HTTPException(status_code=401, detail="phone session required")
    complaints = db.query_by_phone_hash(tid, phone_hash)
    return {
        "reports": [
            {
                "complaint_id": c.complaint_id,
                "category": c.category.value,
                "status": c.status.value,
                "created_at": c.created_at.isoformat(),
                "ward_id": c.ward_id,
            }
            for c in complaints
        ]
    }
