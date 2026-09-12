from datetime import datetime, timedelta, timezone

from wardwatch.agents import escalation
from wardwatch.models import Category, Status

from .factories import make_complaint

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _overdue(days: int, **kw):
    created = NOW - timedelta(days=days + 7)
    return make_complaint(
        created_at=created,
        sla_deadline=NOW - timedelta(days=days),
        category=Category.POTHOLE,
        **kw,
    )


def test_not_breached_is_ignored():
    c = make_complaint(sla_deadline=NOW + timedelta(days=1))
    assert escalation.evaluate([c], NOW) == []


def test_tier1_on_first_breach():
    actions = escalation.evaluate([_overdue(1)], NOW)
    assert len(actions) == 1 and actions[0].new_tier == 1
    assert not actions[0].supervisor_cc


def test_tier2_after_one_more_cycle():
    actions = escalation.evaluate([_overdue(8)], NOW)  # pothole cycle = 7d
    assert actions[0].new_tier == 2 and actions[0].supervisor_cc
    assert actions[0].citizen_msg is not None


def test_tier_caps_at_3():
    actions = escalation.evaluate([_overdue(60)], NOW)
    assert actions[0].new_tier == 3


def test_resolved_never_escalates():
    c = _overdue(30, status=Status.RESOLVED)
    assert escalation.evaluate([c], NOW) == []


def test_apply_bumps_counters():
    c = _overdue(1)
    action = escalation.evaluate([c], NOW)[0]
    escalation.apply(c, action)
    assert c.escalation_tier == 1 and c.escalation_count == 1
