"""EscalationAgent — pure function, no LLM (spec §6, §7).

Tier 1: officer notified via WhatsApp.
Tier 2: still open after tier 1 + one more SLA cycle -> supervisor CC'd, citizen updated.
Tier 3: counts against the public department compliance %.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Complaint, Status, TenantConfig
from ..sla import sla_days


@dataclass
class EscalationAction:
    complaint_id: str
    new_tier: int
    officer_msg: str
    supervisor_cc: bool
    citizen_msg: str | None


def _target_tier(c: Complaint, now: datetime, cycle_days: int) -> int:
    overdue = now - c.sla_deadline
    if overdue < timedelta(0):
        return c.escalation_tier
    # One extra SLA cycle overdue bumps to tier 2, two cycles to tier 3.
    cycles_over = overdue.days // max(cycle_days, 1)
    return min(1 + cycles_over, 3)


def evaluate(
    complaints: list[Complaint], now: datetime, config: TenantConfig | None = None
) -> list[EscalationAction]:
    actions: list[EscalationAction] = []
    for c in complaints:
        if c.status == Status.RESOLVED or now <= c.sla_deadline:
            continue
        cycle = sla_days(c.category, config)
        tier = _target_tier(c, now, cycle)
        if tier <= c.escalation_tier:
            continue
        actions.append(
            EscalationAction(
                complaint_id=c.complaint_id,
                new_tier=tier,
                officer_msg=(
                    f"[Tier {tier}] {c.complaint_id} ({c.category.value}) breached SLA "
                    f"on {c.sla_deadline:%Y-%m-%d}. Please act."
                ),
                supervisor_cc=tier >= 2,
                citizen_msg=(
                    f"Your report {c.complaint_id} is overdue and has been escalated. "
                    "The ward office has been re-notified."
                    if tier >= 2
                    else None
                ),
            )
        )
    return actions


def apply(c: Complaint, action: EscalationAction) -> Complaint:
    c.escalation_tier = action.new_tier
    c.escalation_count += 1
    return c
