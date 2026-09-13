from fastapi.testclient import TestClient

from wardwatch import db
from wardwatch.api.app import create_app
from wardwatch.ids import hash_phone
from wardwatch.config import get_settings

from .test_pipeline import _tiny_jpeg


def _payload(message: dict) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}


def test_whatsapp_assembles_photo_and_voice_across_messages(fakes, monkeypatch):
    from wardwatch.api import routes_webhook

    monkeypatch.setattr(routes_webhook, "_download_media", lambda media_id: _tiny_jpeg())
    client = TestClient(create_app())
    phone = "919000011111"

    first = client.post(
        "/webhook/whatsapp",
        json=_payload({"from": phone, "type": "image", "image": {"id": "photo-1"}}),
    )
    assert first.status_code == 200
    assert db.get_inbound_session("MDU-CORP", hash_phone(phone)) is not None
    assert "description" in fakes.sent[-1][1].lower()

    second = client.post(
        "/webhook/whatsapp",
        json=_payload({"from": phone, "type": "audio", "audio": {"id": "audio-1"}}),
    )
    assert second.status_code == 200
    assert db.get_inbound_session("MDU-CORP", hash_phone(phone)) is None
    complaints = db.query_ward("MDU-CORP", "MDU-W14")
    assert len(complaints) == 1
    assert complaints[0].photo_s3_key
    assert "Logged as" in fakes.sent[-1][1]


def test_tamil_incomplete_message_gets_tamil_reply(fakes):
    client = TestClient(create_app())
    client.post(
        "/webhook/whatsapp",
        json=_payload({"from": "919000022222", "type": "text", "text": {"body": "சாலையில் குழி உள்ளது"}}),
    )
    assert "புகைப்படத்தை" in fakes.sent[-1][1]


def test_webhook_signature_is_enforced(fakes, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    get_settings.cache_clear()
    response = TestClient(create_app()).post(
        "/webhook/whatsapp",
        json=_payload({"from": "1", "type": "text", "text": {"body": "test"}}),
        headers={"X-Hub-Signature-256": "sha256=wrong"},
    )
    assert response.status_code == 401
