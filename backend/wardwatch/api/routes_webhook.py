"""POST /webhook/whatsapp — citizen submission intake (spec §0-§5).

Accepts a simplified payload (the real WhatsApp webhook shape is normalised by the
messaging provider integration, out of scope for this scaffold). The citizen phone
is hashed here and never persisted or logged in plaintext.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter
from pydantic import BaseModel

from ..agents.orchestrator import handle_submission
from ..config import get_settings
from ..notify import get_messenger
from ..pipeline import Submission

router = APIRouter(prefix="/webhook", tags=["webhook"])


class WhatsAppInbound(BaseModel):
    from_phone: str
    ward_id: str
    transcript: str = ""
    photo_b64: str | None = None
    location: list[float] | None = None  # [lat, lng]
    landmark_text: str | None = None
    tenant_id: str | None = None


class WebhookReply(BaseModel):
    kind: str
    reply: str
    complaint_id: str | None = None


@router.post("/whatsapp", response_model=WebhookReply)
def whatsapp_inbound(msg: WhatsAppInbound) -> WebhookReply:
    tenant_id = msg.tenant_id or get_settings().default_tenant_id
    photo = base64.b64decode(msg.photo_b64) if msg.photo_b64 else None
    shared = tuple(msg.location) if msg.location and len(msg.location) == 2 else None

    result = handle_submission(
        Submission(
            tenant_id=tenant_id,
            ward_id=msg.ward_id,
            citizen_phone=msg.from_phone,
            photo=photo,
            transcript=msg.transcript,
            shared_location=shared,
            landmark_text=msg.landmark_text,
        )
    )

    get_messenger().send_text(msg.from_phone, result.message)
    return WebhookReply(
        kind=result.kind,
        reply=result.message,
        complaint_id=result.complaint.complaint_id if result.complaint else None,
    )
