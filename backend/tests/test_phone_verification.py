from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from wardwatch import db, notify
from wardwatch.agents.orchestrator import handle_submission
from wardwatch.api.app import create_app
from wardwatch.ids import hash_phone
from wardwatch.models import OtpChallenge
from wardwatch.notify import FakeWhatsAppOtp, set_whatsapp_otp_sender
from wardwatch.config import get_settings
from wardwatch.pipeline import Submission

TENANT = "MDU-CORP"
PHONE = "+91 90000 11111"


def _sub(**kw):
    base = dict(
        tenant_id=TENANT,
        ward_id="MDU-W14",
        citizen_phone=PHONE,
        photo=None,
        transcript="huge pothole near the bus stand blocking traffic",
        shared_location=(9.9252, 78.1198),
    )
    base.update(kw)
    return Submission(**base)


def _otp_sender() -> FakeWhatsAppOtp:
    fake = FakeWhatsAppOtp()
    set_whatsapp_otp_sender(fake)
    return fake


def _client():
    return TestClient(create_app())


def test_otp_request_sends_via_fake_whatsapp():
    fake = _otp_sender()
    client = _client()
    resp = client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    assert resp.status_code == 200
    assert resp.json() == {"sent": True}
    assert len(fake.sent) == 1
    to, code = fake.sent[0]
    assert to == "+919000011111"
    assert len(code) == 6 and code.isdigit()


def test_otp_request_rejects_non_indian_phone_number():
    _otp_sender()
    response = _client().post(
        "/public/verify-phone/request",
        json={"tenant_id": TENANT, "phone": "+14155552671"},
    )
    assert response.status_code == 422


def test_otp_request_normalizes_local_indian_number():
    fake = _otp_sender()
    response = _client().post(
        "/public/verify-phone/request",
        json={"tenant_id": TENANT, "phone": "9000011111"},
    )
    assert response.status_code == 200
    assert fake.sent[0][0] == "+919000011111"


def test_otp_request_fails_closed_when_whatsapp_is_not_configured():
    set_whatsapp_otp_sender(None)
    response = _client().post(
        "/public/verify-phone/request",
        json={"tenant_id": TENANT, "phone": "9000011111"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "WhatsApp OTP is not configured"
    assert db.get_otp_challenge(TENANT, hash_phone("+919000011111")) is None


def test_meta_whatsapp_otp_uses_authentication_template(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    monkeypatch.setenv("WHATSAPP_OTP_TEMPLATE_NAME", "wardwatch_login_otp")
    get_settings.cache_clear()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, *, json, headers, timeout):
        captured.update(url=url, payload=json, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(notify.httpx, "post", fake_post)
    notify.MetaWhatsAppOtp().send_otp("+919000011111", "123456")

    assert captured["payload"]["to"] == "919000011111"
    template = captured["payload"]["template"]
    assert template["name"] == "wardwatch_login_otp"
    assert template["components"][0]["parameters"][0]["text"] == "123456"
    assert template["components"][1]["sub_type"] == "url"


def _requested_code(fake: FakeWhatsAppOtp) -> str:
    return fake.sent[-1][1]


def test_confirm_with_correct_code_succeeds_and_session_works():
    fake = _otp_sender()
    handle_submission(_sub())
    client = _client()
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    code = _requested_code(fake)

    resp = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": PHONE, "code": code},
    )
    assert resp.status_code == 200
    token = resp.json()["session_token"]
    assert token

    my = client.get("/public/my-reports", params={"tenant_id": TENANT}, headers={"X-Phone-Session": token})
    assert my.status_code == 200
    reports = my.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["category"] == "pothole"


def test_confirm_with_wrong_code_fails_and_increments_attempts():
    _otp_sender()
    client = _client()
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})

    resp = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": PHONE, "code": "000000"},
    )
    assert resp.status_code == 400
    challenge = db.get_otp_challenge(TENANT, hash_phone(PHONE))
    assert challenge is not None
    assert challenge.attempts == 1


def test_confirm_with_expired_challenge_fails():
    phone_hash = hash_phone(PHONE)
    now = datetime.now(timezone.utc)
    challenge = OtpChallenge(
        tenant_id=TENANT,
        phone_hash=phone_hash,
        code_hash="doesnotmatter",
        attempts=0,
        created_at=now - timedelta(minutes=20),
        expires_at=int((now - timedelta(minutes=10)).timestamp()),
    )
    db.create_otp_challenge(challenge)

    client = _client()
    resp = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": PHONE, "code": "123456"},
    )
    assert resp.status_code == 400
    assert db.get_otp_challenge(TENANT, phone_hash) is None


def test_five_failed_attempts_invalidates_challenge():
    _otp_sender()
    client = _client()
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})

    for _ in range(5):
        resp = client.post(
            "/public/verify-phone/confirm",
            json={"tenant_id": TENANT, "phone": PHONE, "code": "000000"},
        )
        assert resp.status_code == 400

    assert db.get_otp_challenge(TENANT, hash_phone(PHONE)) is None


def test_resend_cooldown_rejects_too_soon_second_request():
    _otp_sender()
    client = _client()
    first = client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    assert first.status_code == 200

    second = client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    assert second.status_code == 429


def test_my_reports_scoped_to_phone_and_tenant():
    fake = _otp_sender()
    other_phone = "+91 90000 22222"
    handle_submission(_sub(citizen_phone=PHONE))
    handle_submission(_sub(citizen_phone=other_phone, shared_location=(9.94, 78.15)))

    client = _client()
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    code = _requested_code(fake)
    token = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": PHONE, "code": code},
    ).json()["session_token"]

    my = client.get("/public/my-reports", params={"tenant_id": TENANT}, headers={"X-Phone-Session": token})
    reports = my.json()["reports"]
    assert len(reports) == 1

    my_complaint = db.query_by_phone_hash(TENANT, hash_phone(PHONE))[0]
    other_complaint = db.query_by_phone_hash(TENANT, hash_phone(other_phone))[0]
    assert reports[0]["complaint_id"] == my_complaint.complaint_id
    assert reports[0]["complaint_id"] != other_complaint.complaint_id


def test_my_reports_with_invalid_or_expired_session_returns_401():
    client = _client()
    resp = client.get(
        "/public/my-reports", params={"tenant_id": TENANT}, headers={"X-Phone-Session": "bogus-token"}
    )
    assert resp.status_code == 401

    resp_no_header = client.get("/public/my-reports", params={"tenant_id": TENANT})
    assert resp_no_header.status_code == 401


def test_my_reports_response_excludes_private_fields():
    fake = _otp_sender()
    handle_submission(_sub())
    client = _client()
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": PHONE})
    code = _requested_code(fake)
    token = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": PHONE, "code": code},
    ).json()["session_token"]

    my = client.get("/public/my-reports", params={"tenant_id": TENANT}, headers={"X-Phone-Session": token})
    body_str = str(my.json())
    assert "citizen_contact_ciphertexts" not in body_str
    assert "citizen_phone_hash" not in body_str
    assert "evidence" not in body_str
    assert "photo_s3_key" not in body_str
