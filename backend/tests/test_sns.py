"""SNS SMS notification channel: dispatch, idempotency/retry, and that the
existing WhatsApp/email channels are unaffected (spec §7)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import boto3

from wardwatch import db, notify
from wardwatch.agents.orchestrator import handle_submission
from wardwatch.config import get_settings
from wardwatch.models import NotifyOutcome
from wardwatch.notify import FakeSns, set_sns_client
from wardwatch.pipeline import Submission
from wardwatch.schedulers import escalation_sweep


def _sub(**kw):
    base = dict(
        tenant_id="MDU-CORP",
        ward_id="MDU-W14",
        citizen_phone="+91 90000 11111",
        photo=None,
        transcript="huge pothole near the bus stand blocking traffic",
        shared_location=(9.9252, 78.1198),
    )
    base.update(kw)
    return Submission(**base)


def _configure_kms(monkeypatch):
    key = boto3.client("kms", region_name="ap-south-1").create_key()["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("CONTACT_KMS_KEY_ID", key)
    get_settings.cache_clear()


def _make_overdue(complaint):
    # Pothole's SLA cycle is 7 days; tier 2 (the first tier with a citizen_msg,
    # per escalation.evaluate) requires at least one full extra cycle overdue.
    complaint.sla_deadline = datetime.now(timezone.utc) - timedelta(days=8)
    db.put_complaint(complaint)


def test_sms_dispatch_for_phone_only_web_citizen(fakes, monkeypatch):
    """A web citizen who supplies contact_phone (no WhatsApp thread) is stored
    with the "sms" channel and gets escalation updates through SNS."""
    _configure_kms(monkeypatch)
    fake_sns = FakeSns()
    set_sns_client(fake_sns)
    try:
        c = handle_submission(
            _sub(citizen_phone="web-anonymous", contact_phone="+919000033333")
        ).complaint
        assert c.citizen_contact_channels == ["sms"]

        _make_overdue(c)
        result = escalation_sweep.run_sweep()
        assert result["escalations"] == 1

        assert len(fake_sns.sent) == 1
        to, body = fake_sns.sent[0]
        assert to == "+919000033333"
        assert body

        # WhatsApp fake got nothing for this citizen — SMS was used instead.
        assert fakes.sent == []

        reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
        assert reloaded.citizen_notify_log[-1].outcome == NotifyOutcome.SENT
    finally:
        set_sns_client(None)


def test_sms_idempotent_on_repeat_sweep(fakes, monkeypatch):
    """Re-running the sweep for the same escalation tier must not re-send."""
    _configure_kms(monkeypatch)
    fake_sns = FakeSns()
    set_sns_client(fake_sns)
    try:
        c = handle_submission(
            _sub(citizen_phone="web-anonymous", contact_phone="+919000044444")
        ).complaint
        _make_overdue(c)

        escalation_sweep.run_sweep()
        assert len(fake_sns.sent) == 1

        # Second sweep run at the same tier: already_sent guard in run_sweep
        # skips re-sending, reusing the existing citizen_notify_log check.
        reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
        escalation_sweep.run_sweep()
        assert len(fake_sns.sent) == 1
        reloaded2 = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
        assert len(reloaded2.citizen_notify_log) == len(reloaded.citizen_notify_log)
    finally:
        set_sns_client(None)


def test_sms_retry_then_success_logs_one_sent_attempt(fakes, monkeypatch):
    """The existing NotifyAttempt retry loop (2 attempts) applies to SNS too:
    a first failure followed by success is logged as one SENT attempt."""
    _configure_kms(monkeypatch)

    @dataclass
    class FlakyOnceSns:
        sent: list[tuple[str, str]] = field(default_factory=list)
        _failed_once: bool = False

        def send_text(self, to: str, body: str) -> None:
            if not self._failed_once:
                self._failed_once = True
                raise RuntimeError("sns transient failure")
            self.sent.append((to, body))

    flaky = FlakyOnceSns()
    set_sns_client(flaky)
    try:
        c = handle_submission(
            _sub(citizen_phone="web-anonymous", contact_phone="+919000055555")
        ).complaint
        _make_overdue(c)

        escalation_sweep.run_sweep()
        assert len(flaky.sent) == 1

        reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
        assert len(reloaded.citizen_notify_log) == 1
        assert reloaded.citizen_notify_log[0].outcome == NotifyOutcome.SENT
    finally:
        set_sns_client(None)


def test_whatsapp_dispatch_unaffected_by_sns_addition(fakes, monkeypatch):
    """A normal WhatsApp citizen (no contact_phone) keeps going through the
    WhatsApp messenger, not SNS."""
    _configure_kms(monkeypatch)
    fake_sns = FakeSns()
    set_sns_client(fake_sns)
    try:
        c = handle_submission(_sub()).complaint
        assert c.citizen_contact_channels == ["whatsapp"]

        _make_overdue(c)
        escalation_sweep.run_sweep()

        assert len(fakes.sent) == 1
        assert fake_sns.sent == []
    finally:
        set_sns_client(None)


def test_email_dispatch_unaffected_by_sns_addition(fakes, monkeypatch):
    """send_contact still routes an '@' address to SES regardless of channel."""
    sent_emails: list[tuple[str, str, str]] = []

    class RecordingSes:
        def send_email(self, to, subject, body):
            sent_emails.append((to, subject, body))

    monkeypatch.setattr(notify, "SesMailer", lambda: RecordingSes())
    notify.send_contact("officer@example.org", "subject", "body", channel="sms")
    assert sent_emails == [("officer@example.org", "subject", "body")]
