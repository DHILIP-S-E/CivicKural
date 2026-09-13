import base64
import io

from fastapi.testclient import TestClient

from wardwatch import aggregates, db
from wardwatch.agents.orchestrator import handle_submission
from wardwatch.api.app import create_app
from wardwatch.ids import hash_phone
from wardwatch.models import Category, Status, StatusEvent
from wardwatch.notify import FakeSns, set_sns_client
from wardwatch.pipeline import Submission

from .factories import make_complaint

TENANT = "MDU-CORP"
REPORTER_PHONE = "+91 90000 66666"


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


def _requested_code(fake: FakeSns) -> str:
    body = fake.sent[-1][1]
    for i in range(len(body) - 5):
        chunk = body[i : i + 6]
        if chunk.isdigit():
            return chunk
    raise AssertionError(f"no 6-digit code found in {body!r}")


def _phone_session(client: TestClient, phone: str = REPORTER_PHONE) -> str:
    """Runs the OTP request/confirm flow and returns a session token, mirroring
    the helper pattern in test_phone_verification.py."""
    fake = FakeSns()
    set_sns_client(fake)
    client.post("/public/verify-phone/request", json={"tenant_id": TENANT, "phone": phone})
    code = _requested_code(fake)
    resp = client.post(
        "/public/verify-phone/confirm",
        json={"tenant_id": TENANT, "phone": phone, "code": code},
    )
    return resp.json()["session_token"]


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


def test_success_metrics_measure_dedup_and_location(fakes):
    first = handle_submission(_sub()).complaint
    first.duplicate_reports_count = 1
    metrics = aggregates.success_metrics([first])
    assert metrics["incoming_reports"] == 2
    assert metrics["auto_deduplicated_pct"] == 50.0
    assert metrics["gps_precise_pct"] == 100.0


def test_community_priority_groups_do_not_expose_complaints(fakes):
    complaint = handle_submission(_sub()).complaint
    complaint.duplicate_reports_count = 2  # report_count = 3, meets k-anonymity threshold
    groups = aggregates.community_priorities([complaint])
    assert groups[0]["report_count"] == 3
    assert complaint.complaint_id not in str(groups)


_LONE_LOCATION = (9.94, 78.15)  # distinct grid cell from the default (9.9252, 78.1198)


def test_lone_complaint_suppressed_from_hotspots_and_priorities(fakes):
    """A single citizen's report must not appear on the public hotspots/priorities
    endpoints (k-anonymity threshold of 3), while a bin with >=3 reports does."""
    lone = make_complaint(lat=_LONE_LOCATION[0], lng=_LONE_LOCATION[1])
    others = [make_complaint() for _ in range(3)]

    hotspots = aggregates.hotspot_density([lone, *others])
    hotspot_counts = {b["count"] for b in hotspots}
    assert 1 not in hotspot_counts
    assert any(count >= 3 for count in hotspot_counts)

    priorities = aggregates.community_priorities([lone, *others])
    priority_counts = {g["report_count"] for g in priorities}
    assert 1 not in priority_counts
    assert any(count >= 3 for count in priority_counts)


def test_public_hotspots_and_priorities_endpoints_suppress_lone_reports(fakes):
    lone = make_complaint(lat=_LONE_LOCATION[0], lng=_LONE_LOCATION[1])
    others = [make_complaint() for _ in range(3)]
    for c in [lone, *others]:
        db.put_complaint(c)

    client = TestClient(create_app())
    hotspots_body = client.get("/public/hotspots").json()
    assert all(b["count"] >= 3 for b in hotspots_body["bins"])
    assert any(b["count"] >= 3 for b in hotspots_body["bins"])

    priorities_body = client.get("/public/community-priorities").json()
    assert all(i["report_count"] >= 3 for i in priorities_body["issues"])
    assert any(i["report_count"] >= 3 for i in priorities_body["issues"])


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
    result = handle_submission(_sub(photo=png, issue_citizen_token=True))
    c = result.complaint
    client = TestClient(create_app())
    assert client.get(f"/public/complaints/{c.complaint_id}").status_code == 403
    resp = client.get(
        f"/public/complaints/{c.complaint_id}",
        headers={"X-Citizen-Token": result.citizen_access_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == c.complaint_id
    assert body["before_photo_url"] is not None
    assert body["after_photo_url"] is None
    assert "citizen_phone_hash" not in body


def test_verify_resolution_confirm(fakes):
    result = handle_submission(_sub(issue_citizen_token=True))
    c = result.complaint
    c.status = Status.RESOLVED
    c.status_history.append(StatusEvent(status=Status.RESOLVED))
    db.put_complaint(c)

    client = TestClient(create_app())
    resp = client.post(
        f"/public/complaints/{c.complaint_id}/verify-resolution",
        headers={"X-Citizen-Token": result.citizen_access_token},
        json={"confirmed": True},
    )
    assert resp.status_code == 200
    reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
    assert reloaded.status == Status.RESOLVED
    assert reloaded.citizen_disputed is False
    assert any("citizen confirmed" in (e.note or "") for e in reloaded.status_history)


def test_verify_resolution_reject_sets_disputed(fakes):
    result = handle_submission(_sub(issue_citizen_token=True))
    c = result.complaint
    c.status = Status.RESOLVED
    c.status_history.append(StatusEvent(status=Status.RESOLVED))
    db.put_complaint(c)

    png = _tiny_jpeg()
    client = TestClient(create_app())
    resp = client.post(
        f"/public/complaints/{c.complaint_id}/verify-resolution",
        headers={"X-Citizen-Token": result.citizen_access_token},
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
    token = _phone_session(client)
    resp = client.post(
        "/public/reports",
        data={"transcript": "", "ward_id": "MDU-W14"},
        files={"audio": ("note.ogg", b"fake-audio-bytes", "audio/ogg")},
        headers={"X-Phone-Session": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "created"
    assert body["citizen_access_token"]
    assert any("streetlight" in p for p in seen_prompts)
    c = db.get_complaint("MDU-CORP", "MDU-W14", body["complaint_id"])
    assert c.category == Category.STREETLIGHT
    assert c.citizen_phone_hash == hash_phone(REPORTER_PHONE)


def test_submit_report_without_phone_session_returns_401(fakes):
    client = TestClient(create_app())
    resp = client.post(
        "/public/reports",
        data={"transcript": "broken streetlight", "ward_id": "MDU-W14"},
    )
    assert resp.status_code == 401


def test_submit_report_with_invalid_phone_session_returns_401(fakes):
    client = TestClient(create_app())
    resp = client.post(
        "/public/reports",
        data={"transcript": "broken streetlight", "ward_id": "MDU-W14"},
        headers={"X-Phone-Session": "bogus-token"},
    )
    assert resp.status_code == 401


def test_submit_report_attributes_to_verified_phone_and_appears_in_my_reports(fakes):
    from wardwatch.llm import set_vision_hook

    set_vision_hook(lambda system_prompt, user_text, images: {
        "category": "streetlight",
        "severity": "medium",
        "description": "Broken streetlight on main road.",
        "needs_clarification": False,
        "clarification_question": None,
    })

    client = TestClient(create_app())
    token = _phone_session(client)
    resp = client.post(
        "/public/reports",
        data={
            "transcript": "broken streetlight on main road",
            "ward_id": "MDU-W14",
            "lat": 9.9252,
            "lng": 78.1198,
        },
        headers={"X-Phone-Session": token},
    )
    assert resp.status_code == 200
    complaint_id = resp.json()["complaint_id"]

    c = db.get_complaint("MDU-CORP", "MDU-W14", complaint_id)
    assert c.citizen_phone_hash == hash_phone(REPORTER_PHONE)

    my = client.get(
        "/public/my-reports", params={"tenant_id": TENANT}, headers={"X-Phone-Session": token}
    )
    assert my.status_code == 200
    report_ids = [r["complaint_id"] for r in my.json()["reports"]]
    assert complaint_id in report_ids


def test_nearby_discovery_is_community_safe(fakes):
    c = handle_submission(_sub()).complaint
    client = TestClient(create_app())
    body = client.get("/public/complaints/nearby?lat=9.9252&lng=78.1198").json()
    item = body["community_issues"][0]
    assert c.complaint_id not in str(item)
    assert "lat" not in item and "lng" not in item and "description" not in item
