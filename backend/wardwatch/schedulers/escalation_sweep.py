"""EventBridge target — escalation sweep, every 6 hours (spec §7)."""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..agents import escalation
from ..config import get_settings
from ..notify import get_messenger
from ..wards import TENANT_WARDS


def run_sweep(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    messenger = get_messenger()
    processed = 0

    for tenant_id in TENANT_WARDS:
        config = db.get_tenant_config(tenant_id)
        breached = db.complaints_past_deadline(tenant_id, now)
        actions = escalation.evaluate(breached, now, config)
        by_id = {c.complaint_id: c for c in breached}
        for action in actions:
            complaint = by_id[action.complaint_id]
            escalation.apply(complaint, action)
            db.put_complaint(complaint)

            dept_contact = config.dept_contacts.get(complaint.routed_dept.value, "")
            if dept_contact:
                messenger.send_text(dept_contact, action.officer_msg)
            processed += 1

    return {"evaluated_tenants": len(TENANT_WARDS), "escalations": processed}


def handler(event, context):  # AWS Lambda entrypoint
    return run_sweep()
