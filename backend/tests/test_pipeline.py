from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from wardwatch import db
from wardwatch.agents import escalation
from wardwatch.api.app import create_app
from wardwatch.api.auth import issue_token
from wardwatch.llm import set_vision_hook
from wardwatch.models import Category, Status
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


def test_create_then_merge(fakes):
    from wardwatch.agents.orchestrator import handle_submission

    r1 = handle_submission(_sub())
    assert r1.kind == "created"
    c = r1.complaint
    assert c.category == Category.POTHOLE
    assert c.routed_dept.value == "roads"
    assert c.geo.source.value == "whatsapp_share"
    assert (c.sla_deadline - c.created_at).days == 7
    assert c.citizen_phone_hash != "+91 90000 11111"

    r2 = handle_submission(_sub(citizen_phone="+91 90000 22222", shared_location=(9.92525, 78.11985)))
    assert r2.kind == "merged"
    assert r2.complaint.complaint_id == c.complaint_id
    assert r2.complaint.duplicate_reports_count == 1


def test_needs_location_when_all_tiers_fail(fakes):
    from wardwatch import geocode
    from wardwatch.agents.orchestrator import handle_submission

    geocode.set_geocode_hook(lambda w, t: None)
    r = handle_submission(_sub(shared_location=None, transcript=""))
    assert r.kind == "needs_location"


def test_escalation_sweep_bumps_tier(fakes):
    from wardwatch.agents.orchestrator import handle_submission

    c = handle_submission(_sub()).complaint
    c.sla_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    db.put_complaint(c)

    result = escalation_sweep.run_sweep()
    assert result["escalations"] == 1
    reloaded = db.get_complaint("MDU-CORP", "MDU-W14", c.complaint_id)
    assert reloaded.escalation_tier == 1 and reloaded.escalation_count == 1


def test_public_endpoint_leaks_no_pii(fakes):
    from wardwatch.agents.orchestrator import handle_submission

    handle_submission(_sub())
    client = TestClient(create_app())
    body = client.get("/public/compliance").text
    assert "90000" not in body
    hs = client.get("/public/hotspots").json()
    assert all(set(b) == {"lat", "lng", "count"} for b in hs["bins"])


def test_officer_token_cannot_read_admin_settings(fakes):
    client = TestClient(create_app())
    tok = issue_token("officer-1", "officer", "MDU-CORP", ["MDU-W14"])
    resp = client.get("/admin/settings", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403


def test_verify_gate(fakes):
    from wardwatch.agents.orchestrator import handle_submission

    # give the complaint a before-photo
    png = _tiny_jpeg()
    c = handle_submission(_sub(photo=png)).complaint
    client = TestClient(create_app())
    tok = issue_token("o", "officer", "MDU-CORP", ["MDU-W14"])
    import base64

    set_vision_hook(lambda **kw: {"resolved": False, "confidence": "low", "reason": "cannot tell"})
    resp = client.post(
        f"/complaints/MDU-W14/{c.complaint_id}/verify",
        headers={"Authorization": f"Bearer {tok}"},
        json={"after_photo_b64": base64.b64encode(png).decode()},
    )
    assert resp.json()["status"] == Status.PENDING_VERIFICATION.value

    set_vision_hook(lambda **kw: {"resolved": True, "confidence": "high", "reason": "filled"})
    resp = client.post(
        f"/complaints/MDU-W14/{c.complaint_id}/verify",
        headers={"Authorization": f"Bearer {tok}"},
        json={"after_photo_b64": base64.b64encode(png).decode()},
    )
    assert resp.json()["status"] == Status.RESOLVED.value


def _tiny_jpeg() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (128, 128, 128)).save(buf, format="JPEG")
    return buf.getvalue()
