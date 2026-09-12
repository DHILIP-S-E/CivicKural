import base64
import io

from fastapi.testclient import TestClient

from wardwatch import aggregates, db
from wardwatch.agents.orchestrator import handle_submission
from wardwatch.api.app import create_app
from wardwatch.models import Category, Status, StatusEvent
from wardwatch.pipeline import Submission


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


def _tiny_jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (128, 128, 128)).save(buf, format="JPEG")
    return buf.getvalue()


# --- Feature 1: dashboard ---

def test_category_totals():
    c = handle_submission(_sub()).complaint
    totals = aggregates.category_totals([c])
    assert totals == {"pothole": 1}


def test_resolution_rate():
    assert aggregates.resolution_rate({"open": 1, "resolved": 1}) == 0.5
    assert aggregates.resolution_rate({}) == 0.0
    assert aggregates.resolution_rate({"open": 3}) == 0.0


def test_dashboard_endpoint(fakes):
    handle_submission(_sub())
    client = TestClient(create_app())
    resp = client.get("/public/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["status_totals"]["open"] == 1
    assert body["resolution_rate"] == 0.0
    assert body["top_categories"][0]["category"] == "pothole"


# --- Feature 2: citizen resolution verification ---

def test_complaint_detail_endpoint(fakes):
    png = _tiny_jpeg()
    c = handle_submission(_sub(photo=png)).complaint
    client = TestClient(create_app())
    resp = client.get(f"/public/complaints/{c.complaint_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == c.complaint_id
    assert body["before_photo_url"] is not None
    assert body["after_photo_url"] is None
    assert "citizen_phone_hash" not in body


def test_verify_resolution_confirm(fakes):
    c = handle_submission(_sub()).complaint
    c.status = Status.RESOLVED
    c.status_history.append(StatusEvent(status=Status.RESOLVED))
    db.put_complaint(c)

    client = TestClient(create_app())
    resp = client.post(
        f"/public/complaints/{c.complaint_id}/verify-resolution",
        json={"confirmed": True},
    )
    assert resp.status_code == 200
    reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
    assert reloaded.status == Status.RESOLVED
    assert reloaded.citizen_disputed is False
    assert any("citizen confirmed" in (e.note or "") for e in reloaded.status_history)


def test_verify_resolution_reject_sets_disputed(fakes):
    c = handle_submission(_sub()).complaint
    c.status = Status.RESOLVED
    c.status_history.append(StatusEvent(status=Status.RESOLVED))
    db.put_complaint(c)

    png = _tiny_jpeg()
    client = TestClient(create_app())
    resp = client.post(
        f"/public/complaints/{c.complaint_id}/verify-resolution",
        json={"confirmed": False, "new_photo_b64": base64.b64encode(png).decode()},
    )
    assert resp.status_code == 200
    reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
    assert reloaded.citizen_disputed is True
    assert reloaded.status == Status.IN_PROGRESS
    assert reloaded.verification_photo_s3_key is not None


# --- Feature 3: voice reporting ---

def test_submit_report_with_audio_transcribes(fakes, monkeypatch):
    from wardwatch import transcribe
    from wardwatch.llm import set_vision_hook

    transcribe.set_transcribe_hook(lambda audio: "there is a broken streetlight on main road")

    seen_prompts = []

    def capture_vision(system_prompt, user_text, images):
        seen_prompts.append(user_text)
        return {
            "category": "streetlight",
            "severity": "medium",
            "description": "Broken streetlight on main road.",
            "needs_clarification": False,
            "clarification_question": None,
        }

    set_vision_hook(capture_vision)

    client = TestClient(create_app())
    resp = client.post(
        "/public/reports",
        data={"transcript": "", "ward_id": "MDU-W14"},
        files={"audio": ("note.ogg", b"fake-audio-bytes", "audio/ogg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "created"
    assert any("streetlight" in p for p in seen_prompts)
    c = db.get_complaint("MDU-CORP", "MDU-W14", body["complaint_id"])
    assert c.category == Category.STREETLIGHT
