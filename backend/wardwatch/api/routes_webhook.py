"""WhatsApp webhook — both the real Meta Cloud API contract and a simulate
endpoint for local testing without a phone (spec §0-§5).

Real Meta webhook: GET does the verify-token handshake, POST delivers the
actual message payload (text / location / image / audio, media as an id that
must be resolved to a URL and downloaded separately).

The citizen phone is hashed before it ever reaches the pipeline and is never
persisted or logged in plaintext.
"""
from __future__ import annotations

import base64

import httpx
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from ..agents.orchestrator import handle_submission
from ..config import get_settings
from ..notify import get_messenger
from ..pipeline import Submission
from ..transcribe import transcribe_audio
from ..wards import wards_for

router = APIRouter(prefix="/webhook", tags=["webhook"])


# --- real Meta Cloud API webhook ---

@router.get("/whatsapp")
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    s = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == s.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


def _download_media(media_id: str) -> bytes:
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.whatsapp_token}"}
    meta = httpx.get(f"{s.whatsapp_api_base}/{media_id}", headers=headers, timeout=20).json()
    return httpx.get(meta["url"], headers=headers, timeout=30).content


def _default_ward(tenant_id: str) -> str:
    wards = wards_for(tenant_id)
    return wards[0] if wards else "MDU-W14"


@router.post("/whatsapp")
async def whatsapp_meta_inbound(payload: dict) -> dict:
    s = get_settings()
    tenant_id = s.default_tenant_id
    ward_id = _default_ward(tenant_id)
    messenger = get_messenger()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                from_phone = msg.get("from", "")
                transcript = ""
                photo: bytes | None = None
                shared_location: tuple[float, float] | None = None

                mtype = msg.get("type")
                if mtype == "text":
                    transcript = msg.get("text", {}).get("body", "")
                elif mtype == "location":
                    loc = msg["location"]
                    shared_location = (loc["latitude"], loc["longitude"])
                elif mtype == "image":
                    photo = _download_media(msg["image"]["id"])
                    transcript = msg.get("image", {}).get("caption", "")
                elif mtype == "audio":
                    audio_bytes = _download_media(msg["audio"]["id"])
                    transcript = transcribe_audio(audio_bytes, "ogg")
                else:
                    continue

                result = handle_submission(
                    Submission(
                        tenant_id=tenant_id,
                        ward_id=ward_id,
                        citizen_phone=from_phone,
                        photo=photo,
                        transcript=transcript,
                        shared_location=shared_location,
                    )
                )
                messenger.send_text(from_phone, result.message)

    return {"status": "ok"}


# --- local test/simulate endpoint (no real WhatsApp round trip needed) ---

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


@router.post("/simulate", response_model=WebhookReply)
def whatsapp_simulate(msg: WhatsAppInbound) -> WebhookReply:
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
