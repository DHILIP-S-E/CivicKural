"""Officer complaint routes — ward-scoped (spec §5)."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import authority, db, storage
from ..agents.verification import verify
from ..models import AuthorityStatus, Complaint, Status, StatusEvent
from .auth import Principal, current_principal, require_operator

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _redact(c: Complaint) -> dict:
    """Officer view: everything except any way back to the citizen identity."""
    d = c.model_dump(mode="json")
    d.pop("citizen_access_hashes", None)
    d.pop("citizen_contact_ciphertexts", None)
    d["citizen_phone_hash"] = c.citizen_phone_hash[:8] + "…"
    if c.photo_s3_key:
        d["photo_url"] = storage.presigned_url(c.photo_s3_key)
    if c.verification_photo_s3_key:
        d["verification_photo_url"] = storage.presigned_url(c.verification_photo_s3_key)
    return d


@router.get("")
def list_queue(
    ward_id: str,
    status: Status | None = None,
    p: Principal = Depends(current_principal),
) -> list[dict]:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    items = db.query_ward(p.tenant_id, ward_id)
    if status:
        items = [c for c in items if c.status == status]
    return [_redact(c) for c in sorted(items, key=lambda c: c.sla_deadline)]


@router.get("/{ward_id}/infra-flags")
def infra_flags(ward_id: str, p: Principal = Depends(current_principal)) -> list[dict]:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    return [f.model_dump(mode="json") for f in db.query_infra_flags(p.tenant_id, ward_id)]


@router.get("/{ward_id}/{complaint_id}")
def detail(
    ward_id: str, complaint_id: str, p: Principal = Depends(current_principal)
) -> dict:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    return _redact(c)


class StatusPatch(BaseModel):
    status: Status
    note: str | None = None


@router.post("/{ward_id}/{complaint_id}/status")
def set_status(
    ward_id: str,
    complaint_id: str,
    patch: StatusPatch,
    p: Principal = Depends(require_operator),
) -> dict:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if patch.status == Status.RESOLVED:
        raise HTTPException(400, "resolve only via /verify with an after-photo")
    allowed = {
        Status.OPEN: {Status.IN_PROGRESS},
        Status.IN_PROGRESS: {Status.OPEN, Status.PENDING_VERIFICATION},
        Status.PENDING_VERIFICATION: {Status.IN_PROGRESS},
        Status.RESOLVED: set(),
    }
    if patch.status != c.status and patch.status not in allowed[c.status]:
        raise HTTPException(400, f"invalid status transition: {c.status.value} -> {patch.status.value}")
    c.status = patch.status
    c.status_history.append(
        StatusEvent(status=patch.status, note=patch.note, source=f"user:{p.sub}")
    )
    db.put_complaint(c)
    return _redact(c)


class VerifyBody(BaseModel):
    after_photo_b64: str


@router.post("/{ward_id}/{complaint_id}/verify")
def verify_resolution(
    ward_id: str,
    complaint_id: str,
    body: VerifyBody,
    p: Principal = Depends(require_operator),
) -> dict:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if not c.photo_s3_key:
        raise HTTPException(400, "no before-photo to compare against")

    try:
        after = base64.b64decode(body.after_photo_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "invalid after-photo encoding")
    if not after or len(after) > 10 * 1024 * 1024:
        raise HTTPException(413, "after-photo must be between 1 byte and 10 MB")
    before = storage.get_photo(c.photo_s3_key)
    outcome = verify(c.category, before, after)

    key = storage.photo_key(c.tenant_id, c.complaint_id, "after")
    storage.put_photo(key, after)
    c.verification_photo_s3_key = key
    c.status = outcome.status
    c.verification_confidence = outcome.confidence
    c.verification_reason = outcome.reason
    c.resolved_at = datetime.now(timezone.utc) if outcome.status == Status.RESOLVED else None
    c.status_history.append(
        StatusEvent(
            status=outcome.status,
            note=f"verification: {outcome.reason}",
            source=f"verification_agent:user:{p.sub}",
        )
    )
    db.put_complaint(c)
    return {"outcome": outcome.__dict__, **_redact(c)}


class AuthoritySubmitBody(BaseModel):
    approved: bool


@router.post("/{ward_id}/{complaint_id}/authority-submit")
def submit_to_authority(
    ward_id: str,
    complaint_id: str,
    body: AuthoritySubmitBody,
    p: Principal = Depends(require_operator),
) -> dict:
    """Human-approved adapter boundary for consequential external submission."""
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    if not body.approved:
        raise HTTPException(400, "explicit approval is required")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if c.authority_ticket_id:
        return {"simulated": True, "ticket_id": c.authority_ticket_id, **_redact(c)}
    receipt = authority.submit(c)
    c.authority_ticket_id = receipt.ticket_id
    c.authority_status = AuthorityStatus.SUBMITTED
    c.status_history.append(
        StatusEvent(
            status=c.status,
            note=f"submitted to simulated authority as {receipt.ticket_id}",
            source=f"user:{p.sub}",
        )
    )
    db.put_complaint(c)
    return {"simulated": receipt.simulated, "ticket_id": receipt.ticket_id, **_redact(c)}


class AuthorityStatusBody(BaseModel):
    status: AuthorityStatus


@router.post("/{ward_id}/{complaint_id}/authority-status")
def update_authority_status(
    ward_id: str,
    complaint_id: str,
    body: AuthorityStatusBody,
    p: Principal = Depends(require_operator),
) -> dict:
    """Simulated authority callback used to demonstrate background monitoring."""
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if not c.authority_ticket_id:
        raise HTTPException(400, "complaint has not been submitted to the authority")
    c.authority_status = body.status
    if body.status == AuthorityStatus.IN_PROGRESS and c.status == Status.OPEN:
        c.status = Status.IN_PROGRESS
    elif body.status == AuthorityStatus.EVIDENCE_REQUESTED:
        c.citizen_updates.append("The authority requested additional evidence for this issue.")
    elif body.status == AuthorityStatus.RESOLVED:
        c.status = Status.PENDING_VERIFICATION
        c.citizen_updates.append(
            "The authority marked this issue resolved. Verification evidence is still required."
        )
    c.status_history.append(
        StatusEvent(
            status=c.status,
            note=f"simulated authority status: {body.status.value}",
            source="simulated_authority",
        )
    )
    db.put_complaint(c)
    return _redact(c)
