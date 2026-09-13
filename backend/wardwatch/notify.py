"""Notification channels: WhatsApp Business Cloud API + SES + SNS SMS (spec §7).

If WHATSAPP_TOKEN is unset, FakeWhatsApp is used so the pipeline runs offline.
If SNS_ENABLED is not set, FakeSns is used so the pipeline runs offline.
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


@dataclass
class FakeSns:
    """In-process SNS SMS client used in tests and when SNS_ENABLED is unset."""

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


class SnsSms:
    def __init__(self) -> None:
        s = get_settings()
        self._client = boto3.client("sns", region_name=s.aws_region)

    def send_text(self, to: str, body: str) -> None:
        self._client.publish(PhoneNumber=to, Message=body)


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
_sns_client: Messenger | None = None


def get_messenger() -> Messenger:
    global _messenger
    if _messenger is None:
        _messenger = WhatsAppCloud() if get_settings().whatsapp_enabled else FakeWhatsApp()
    return _messenger


def set_messenger(m: Messenger) -> None:
    """Test hook."""
    global _messenger
    _messenger = m


def get_sns_client() -> Messenger:
    global _sns_client
    if _sns_client is None:
        _sns_client = SnsSms() if get_settings().sns_enabled else FakeSns()
    return _sns_client


def set_sns_client(m: Messenger) -> None:
    """Test hook."""
    global _sns_client
    _sns_client = m


def send_contact(contact: str, subject: str, body: str, channel: str | None = None) -> None:
    """Send to an email address through SES, or to a phone through SNS SMS or
    WhatsApp depending on `channel` ("sms" routes via SNS; anything else, or no
    channel at all, keeps the original WhatsApp behavior)."""
    if not contact:
        return
    if "@" in contact:
        SesMailer().send_email(contact, subject, body)
    elif channel == "sms":
        get_sns_client().send_text(contact, body)
    else:
        get_messenger().send_text(contact, body)
