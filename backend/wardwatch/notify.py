"""Notification channels: WhatsApp Business Cloud API + SES (spec §7).

If WHATSAPP_TOKEN is unset, FakeWhatsApp is used so the pipeline runs offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import boto3
import httpx

from .config import get_settings


class Messenger(Protocol):
    def send_text(self, to: str, body: str) -> None: ...


@dataclass
class FakeWhatsApp:
    """In-process messenger used in tests and when no token is configured."""

    sent: list[tuple[str, str]] = field(default_factory=list)

    def send_text(self, to: str, body: str) -> None:
        self.sent.append((to, body))


class WhatsAppCloud:
    def __init__(self) -> None:
        s = get_settings()
        self._url = f"{s.whatsapp_api_base}/{s.whatsapp_phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {s.whatsapp_token}"}

    def send_text(self, to: str, body: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        httpx.post(self._url, json=payload, headers=self._headers, timeout=15).raise_for_status()


class SesMailer:
    def __init__(self) -> None:
        s = get_settings()
        self._client = boto3.client("ses", region_name=s.aws_region)
        self._sender = s.ses_sender

    def send_email(self, to: str, subject: str, body: str) -> None:
        self._client.send_email(
            Source=self._sender,
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
        )


_messenger: Messenger | None = None


def get_messenger() -> Messenger:
    global _messenger
    if _messenger is None:
        _messenger = WhatsAppCloud() if get_settings().whatsapp_enabled else FakeWhatsApp()
    return _messenger


def set_messenger(m: Messenger) -> None:
    """Test hook."""
    global _messenger
    _messenger = m
