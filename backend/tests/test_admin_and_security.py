"""Tests for the security/ops gaps closed in this change:

- /webhook/simulate auth gate
- JWT expiry enforcement
- escalation-sweep citizen-notify idempotency
- /admin/health endpoint
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from wardwatch import db
from wardwatch.api.app import create_app
from wardwatch.api.auth import issue_token
from wardwatch.config import get_settings
from wardwatch.models import NotifyOutcome
from wardwatch.schedulers import escalation_sweep

from .factories import make_complaint


def _sim_payload(**kw):
    base = dict(
        from_phone="+91 90000 11111",
        ward_id="MDU-W14",
        transcript="huge pothole near the bus stand blocking traffic",
    )
    base.update(kw)
    return base


# --- /webhook/simulate auth gate ---

def test_simulate_disabled_without_flag_or_auth(fakes, monkeypatch):
    monkeypatch.setenv("ENABLE_SIMULATE_ENDPOINT", "false")
    get_settings.cache_clear()
    client = TestClient(create_app())
    resp = client.post("/webhook/simulate", json=_sim_payload())
    assert resp.status_code == 403
    get_settings.cache_clear()


def test_simulate_allowed_with_operator_token_even_if_flag_off(fakes, monkeypatch):
    monkeypatch.setenv("ENABLE_SIMULATE_ENDPOINT", "false")
    get_settings.cache_clear()
    client = TestClient(create_app())
    tok = issue_token("officer-1", "officer", "MDU-CORP", ["MDU-W14"])
    resp = client.post(
        "/webhook/simulate",
        json=_sim_payload(),
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    get_settings.cache_clear()


def test_simulate_allowed_when_flag_enabled_no_auth(fakes):
    # conftest sets ENABLE_SIMULATE_ENDPOINT=true by default for the test suite.
    client = TestClient(create_app())
    resp = client.post("/webhook/simulate", json=_sim_payload())
    assert resp.status_code == 200


# --- JWT expiry ---

def test_issued_token_carries_expiry_and_is_accepted(fakes):
    client = TestClient(create_app())
    tok = issue_token("officer-1", "officer", "MDU-CORP", ["MDU-W14"])
    s = get_settings()
    claims = jwt.decode(tok, s.jwt_secret, algorithms=[s.jwt_algorithm])
    assert "exp" in claims
    resp = client.get("/admin/settings", headers={"Authorization": f"Bearer {tok}"})
    # officer role -> 403 (not admin), but token itself must be accepted (not 401)
    assert resp.status_code == 403


def test_expired_token_is_rejected(fakes):
    s = get_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "officer-1",
            "role": "admin",
            "tenant_id": "MDU-CORP",
            "wards": ["MDU-W14"],
            "iat": now - timedelta(hours=13),
            "exp": now - timedelta(hours=1),
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    client = TestClient(create_app())
    resp = client.get("/admin/settings", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


# --- escalation sweep idempotency ---

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _tier2_complaint():
    created = NOW - timedelta(days=15)
    return make_complaint(
        created_at=created,
        sla_deadline=NOW - timedelta(days=8),  # pothole cycle=7d -> tier 2
    )


def test_sweep_does_not_double_notify_citizen_on_rerun(fakes):
    c = _tier2_complaint()
    db.put_complaint(c)

    escalation_sweep.run_sweep(NOW)
    reloaded = db.get_complaint(c.tenant_id, c.ward_id, c.complaint_id)
    assert reloaded.escalation_tier == 2
    sent_after_first = [
        e for e in reloaded.citizen_notify_log if e.outcome == NotifyOutcome.SENT
    ]
    assert len(sent_after_first) == 1
    updates_after_first = len(reloaded.citizen_updates)

    # Re-run the sweep at the same "now". escalation.evaluate() will no longer
    # propose an action for this complaint (tier already applied), so nothing
    # should be appended again.
    escalation_sweep.run_sweep(NOW)
    reloaded_again = db.get_complaint(c.tenant_id, c.ward_id, c.complaint_id)
    assert len(reloaded_again.citizen_updates) == updates_after_first
    assert len(
        [e for e in reloaded_again.citizen_notify_log if e.outcome == NotifyOutcome.SENT]
    ) == 1


def test_sweep_skips_resend_when_log_already_shows_sent_for_tier(fakes, monkeypatch):
    from wardwatch.agents import escalation as escalation_agent

    c = _tier2_complaint()
    db.put_complaint(c)

    calls = {"n": 0}
    real_evaluate = escalation_agent.evaluate

    def _evaluate_always_tier2(complaints, now, config=None):
        actions = real_evaluate(complaints, now, config)
        return actions

    # First run performs the real send and records SENT for tier 2.
    escalation_sweep.run_sweep(NOW)
    reloaded = db.get_complaint(c.tenant_id, c.ward_id, c.complaint_id)
    assert any(e.outcome == NotifyOutcome.SENT and e.tier == 2 for e in reloaded.citizen_notify_log)

    # Force evaluate() to propose the same tier-2 action again (simulating a
    # scheduler re-run before the tier bump was durably reflected elsewhere),
    # and assert the notify log guard prevents a second send being recorded.
    from wardwatch.agents.escalation import EscalationAction

    monkeypatch.setattr(
        escalation_agent,
        "evaluate",
        lambda complaints, now, config=None: [
            EscalationAction(
                complaint_id=reloaded.complaint_id,
                new_tier=2,
                officer_msg="repeat",
                supervisor_cc=True,
                citizen_msg="repeat update",
            )
        ],
    )
    escalation_sweep.run_sweep(NOW)
    final = db.get_complaint(c.tenant_id, c.ward_id, c.complaint_id)
    sent_entries = [e for e in final.citizen_notify_log if e.outcome == NotifyOutcome.SENT and e.tier == 2]
    assert len(sent_entries) == 1
    assert "repeat update" not in final.citizen_updates


# --- /admin/health ---

def test_admin_health_requires_admin(fakes):
    client = TestClient(create_app())
    tok = issue_token("o", "officer", "MDU-CORP", ["MDU-W14"])
    resp = client.get("/admin/health", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403


def test_admin_health_reports_sweep_times_and_failures(fakes):
    c = _tier2_complaint()
    db.put_complaint(c)
    escalation_sweep.run_sweep(NOW)

    from wardwatch.schedulers import pattern_sweep

    pattern_sweep.run_sweep(NOW)

    client = TestClient(create_app())
    tok = issue_token("admin-1", "admin", "MDU-CORP", ["MDU-W14"])
    resp = client.get("/admin/health", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["last_escalation_sweep_at"] is not None
    assert body["last_pattern_sweep_at"] is not None
    assert "recent_notification_failures" in body
