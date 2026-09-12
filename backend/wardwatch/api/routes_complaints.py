"""Officer complaint routes — ward-scoped (spec §5)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db, storage
from ..agents.verification import verify
from ..models import Complaint, Status, StatusEvent
from .auth import Principal, current_principal

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _redact(c: Complaint) -> dict:
    """Officer view: everything except any way back to the citizen identity."""
    d = c.model_dump(mode="json")
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
    p: Principal = Depends(current_principal),
) -> dict:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if patch.status == Status.RESOLVED:
        raise HTTPException(400, "resolve only via /verify with an after-photo")
    c.status = patch.status
    c.status_history.append(StatusEvent(status=patch.status, note=patch.note))
    db.put_complaint(c)
    return _redact(c)


class VerifyBody(BaseModel):
    after_photo_b64: str


@router.post("/{ward_id}/{complaint_id}/verify")
def verify_resolution(
    ward_id: str,
    complaint_id: str,
    body: VerifyBody,
    p: Principal = Depends(current_principal),
) -> dict:
    if not p.can_see_ward(ward_id):
        raise HTTPException(403, "ward not in scope")
    c = db.get_complaint(p.tenant_id, ward_id, complaint_id)
    if not c:
        raise HTTPException(404, "not found")
    if not c.photo_s3_key:
        raise HTTPException(400, "no before-photo to compare against")

    after = base64.b64decode(body.after_photo_b64)
    before = storage.get_photo(c.photo_s3_key)
    outcome = verify(c.category, before, after)

    key = storage.photo_key(c.tenant_id, c.complaint_id, "after")
    storage.put_photo(key, after)
    c.verification_photo_s3_key = key
    c.status = outcome.status
    c.status_history.append(
        StatusEvent(status=outcome.status, note=f"verification: {outcome.reason}")
    )
    db.put_complaint(c)
    return {"outcome": outcome.__dict__, **_redact(c)}
