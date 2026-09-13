"""EventBridge target — escalation sweep, every 6 hours (spec §7)."""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..agents import escalation
from ..config import get_settings
from ..models import NotifyAttempt, NotifyOutcome, StatusEvent
from ..contact import reveal
from ..notify import send_contact
from ..wards import TENANT_WARDS

# One retry after the initial attempt before a citizen-notify failure is logged
# and swallowed for this sweep run.
_CITIZEN_NOTIFY_MAX_ATTEMPTS = 2


def _notify_citizen_once(
    ciphertext: str, tenant_id: str, subject: str, body: str, channel: str | None = None
) -> None:
    send_contact(reveal(ciphertext, tenant_id), subject, body, channel=channel)


def run_sweep(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
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
                send_contact(dept_contact, f"WardWatch escalation tier {action.new_tier}", action.officer_msg)
            if action.supervisor_cc:
                supervisor = config.dept_contacts.get(
                    f"{complaint.routed_dept.value}_supervisor", ""
                )
                if supervisor:
                    send_contact(
                        supervisor,
                        f"WardWatch supervisor escalation tier {action.new_tier}",
                        action.officer_msg,
                    )
            if action.citizen_msg:
                already_sent = any(
                    entry.tier == action.new_tier and entry.outcome == NotifyOutcome.SENT
                    for entry in complaint.citizen_notify_log
                )
                if not already_sent:
                    complaint.citizen_updates.append(action.citizen_msg)
                    last_error: Exception | None = None
                    delivered = False
                    for attempt in range(1, _CITIZEN_NOTIFY_MAX_ATTEMPTS + 1):
                        try:
                            channels = complaint.citizen_contact_channels
                            for idx, ciphertext in enumerate(complaint.citizen_contact_ciphertexts):
                                # Records written before citizen_contact_channels existed
                                # have no entry here; default them to "whatsapp".
                                channel = channels[idx] if idx < len(channels) else "whatsapp"
                                _notify_citizen_once(
                                    ciphertext,
                                    complaint.tenant_id,
                                    "WardWatch complaint update",
                                    action.citizen_msg,
                                    channel=channel,
                                )
                            delivered = True
                            break
                        except Exception as exc:  # keep sweep progress; retry once
                            last_error = exc
                    complaint.citizen_notify_log.append(
                        NotifyAttempt(
                            tier=action.new_tier,
                            outcome=NotifyOutcome.SENT if delivered else NotifyOutcome.FAILED,
                            detail=None if delivered else str(last_error),
                        )
                    )
                    complaint.status_history.append(
                        StatusEvent(
                            status=complaint.status,
                            note="citizen delay update queued"
                            if delivered
                            else "citizen delay update failed after retry",
                        )
                    )
                    db.put_complaint(complaint)
            processed += 1

    db.put_sweep_marker("escalation", now)
    return {"evaluated_tenants": len(TENANT_WARDS), "escalations": processed}


def handler(event, context):  # AWS Lambda entrypoint
    return run_sweep()
