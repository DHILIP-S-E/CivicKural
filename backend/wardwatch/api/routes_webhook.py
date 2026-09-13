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
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel

from .. import db, storage
from ..agents.orchestrator import handle_submission
from ..config import get_settings
from ..notify import get_messenger
from ..pipeline import Submission
from ..ids import hash_phone
from ..localize import detect_language, message as citizen_message
from ..models import InboundSession
from ..transcribe import transcribe_audio
from ..wards import wards_for
from .auth import Principal

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
    metadata_response = httpx.get(f"{s.whatsapp_api_base}/{media_id}", headers=headers, timeout=20)
    metadata_response.raise_for_status()
    media_response = httpx.get(metadata_response.json()["url"], headers=headers, timeout=30)
    media_response.raise_for_status()
    return media_response.content


def _default_ward(tenant_id: str) -> str:
    wards = wards_for(tenant_id)
    return wards[0] if wards else "MDU-W14"


@router.post("/whatsapp")
async def whatsapp_meta_inbound(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
) -> dict:
    s = get_settings()
    raw_body = await request.body()
    if s.whatsapp_app_secret:
        expected = "sha256=" + hmac.new(
            s.whatsapp_app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="invalid webhook signature")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON payload")
    tenant_id = s.default_tenant_id
    ward_id = _default_ward(tenant_id)
    messenger = get_messenger()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                from_phone = msg.get("from", "")
                phone_hash = hash_phone(from_phone)
                session = db.get_inbound_session(tenant_id, phone_hash) or InboundSession(
                    tenant_id=tenant_id,
                    ward_id=ward_id,
                    citizen_phone_hash=phone_hash,
                    expires_at=int((datetime.now(timezone.utc) + timedelta(hours=s.whatsapp_session_ttl_hours)).timestamp()),
                )
                photo: bytes | None = storage.get_photo(session.photo_s3_key) if session.photo_s3_key else None

                mtype = msg.get("type")
                if mtype == "text":
                    incoming_text = msg.get("text", {}).get("body", "")
                    if session.awaiting_location:
                        session.landmark_text = incoming_text
                        session.awaiting_location = False
                    else:
                        session.transcript = f"{session.transcript}\n{incoming_text}".strip()
                    session.language = detect_language(session.transcript)
                elif mtype == "location":
                    loc = msg["location"]
                    session.shared_location = (loc["latitude"], loc["longitude"])
                elif mtype == "image":
                    photo = _download_media(msg["image"]["id"])
                    session.photo_s3_key = f"_sessions/{tenant_id}/{phone_hash}/before.jpg"
                    storage.put_photo(session.photo_s3_key, photo)
                    caption = msg.get("image", {}).get("caption", "")
                    session.transcript = f"{session.transcript}\n{caption}".strip()
                    session.language = detect_language(session.transcript)
                elif mtype == "audio":
                    audio_bytes = _download_media(msg["audio"]["id"])
                    voice_text = transcribe_audio(audio_bytes, "ogg")
                    session.transcript = f"{session.transcript}\n{voice_text}".strip()
                    session.language = detect_language(session.transcript)
                else:
                    continue

                if not photo or not session.transcript:
                    db.put_inbound_session(session)
                    key = "need_photo" if session.transcript and not photo else "need_description"
                    messenger.send_text(from_phone, citizen_message(session.language, key))
                    continue

                result = handle_submission(
                    Submission(
                        tenant_id=session.tenant_id,
                        ward_id=session.ward_id,
                        citizen_phone=from_phone,
                        photo=photo,
                        transcript=session.transcript,
                        shared_location=session.shared_location,
                        landmark_text=session.landmark_text,
                    )
                )
                messenger.send_text(from_phone, result.message)
                if result.kind in {"created", "merged"}:
                    db.delete_inbound_session(tenant_id, phone_hash)
                    if session.photo_s3_key:
                        storage.delete_object(session.photo_s3_key)
                else:
                    if result.kind == "needs_location":
                        session.awaiting_location = True
                    db.put_inbound_session(session)

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


def _require_simulate_enabled(request: Request) -> Principal | None:
    """Gate /webhook/simulate: on only when explicitly enabled via env flag, or
    when the caller authenticates as an officer/admin. Unauthenticated production
    traffic must never be able to inject complaints through this test endpoint.
    """
    if get_settings().enable_simulate_endpoint:
        return None
    auth_header = request.headers.get("authorization", "")
    if not auth_header:
        raise HTTPException(status_code=403, detail="simulate endpoint disabled")
    from fastapi.security import HTTPAuthorizationCredentials

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=403, detail="simulate endpoint disabled")
    from .auth import current_principal

    principal = current_principal(HTTPAuthorizationCredentials(scheme=scheme, credentials=token))
    if principal.role not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="officer or admin role required")
    return principal


@router.post("/simulate", response_model=WebhookReply)
def whatsapp_simulate(
    msg: WhatsAppInbound, _: Principal | None = Depends(_require_simulate_enabled)
) -> WebhookReply:
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
