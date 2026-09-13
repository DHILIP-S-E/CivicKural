"""Department-level SLA compliance + hotspot density (spec §5, §10).

Every value here is ward-level or coarser. No individual-complaint field is exposed.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from .models import Complaint, Priority, Status


def dept_sla_compliance(complaints: list[Complaint]) -> dict[str, dict]:
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # dept -> [within_sla, total]
    for c in complaints:
        resolved = c.status == Status.RESOLVED
        if not resolved:
            continue
        last = c.status_history[-1].ts if c.status_history else c.created_at
        within = last <= c.sla_deadline
        t = tally[c.routed_dept.value]
        t[1] += 1
        if within:
            t[0] += 1
    result = {
        dept: {
            "resolved_within_sla_pct": round(100 * w / total) if total else None,
            "resolved_count": total,
        }
        for dept, (w, total) in tally.items()
    }
    for c in complaints:
        dept = c.routed_dept.value
        entry = result.setdefault(
            dept, {"resolved_within_sla_pct": None, "resolved_count": 0}
        )
        entry["total_count"] = entry.get("total_count", 0) + 1
        if c.escalation_tier >= 3:
            entry["tier3_breach_count"] = entry.get("tier3_breach_count", 0) + 1
        else:
            entry.setdefault("tier3_breach_count", 0)
    return result


def status_totals(complaints: list[Complaint]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in complaints:
        out[c.status.value] += 1
    return dict(out)


def category_totals(complaints: list[Complaint]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in complaints:
        out[c.category.value] += 1
    return dict(out)


def resolution_rate(totals: dict) -> float:
    total = sum(totals.values())
    if not total:
        return 0.0
    resolved = totals.get(Status.RESOLVED.value, 0)
    return resolved / total


K_ANONYMITY_THRESHOLD = 3


def hotspot_density(complaints: list[Complaint], precision: int = 3) -> list[dict]:
    """Grid-binned counts only — coordinates rounded so nothing pinpoints an address.

    Bins below K_ANONYMITY_THRESHOLD are suppressed so a lone complaint can never
    be traced back to a near-exact location from the public endpoint.
    """
    bins: dict[tuple[float, float], int] = defaultdict(int)
    for c in complaints:
        key = (round(c.geo.lat, precision), round(c.geo.lng, precision))
        bins[key] += 1
    return [
        {"lat": k[0], "lng": k[1], "count": v}
        for k, v in bins.items()
        if v >= K_ANONYMITY_THRESHOLD
    ]


def success_metrics(complaints: list[Complaint]) -> dict[str, float | int | None]:
    """The four measurable WardWatch outcomes from the product specification."""
    if not complaints:
        return {
            "incoming_reports": 0,
            "auto_deduplicated_pct": 0.0,
            "median_first_action_hours": None,
            "sla_breach_rate_pct": 0.0,
            "gps_precise_pct": 0.0,
        }
    duplicate_reports = sum(c.duplicate_reports_count for c in complaints)
    incoming = len(complaints) + duplicate_reports
    action_hours: list[float] = []
    for c in complaints:
        first = next((event for event in c.status_history if event.status != Status.OPEN), None)
        if first:
            action_hours.append((first.ts - c.created_at).total_seconds() / 3600)
    precise = sum(c.geo.source.value in {"whatsapp_share", "exif"} for c in complaints)
    breached = sum(c.escalation_tier > 0 for c in complaints)
    return {
        "incoming_reports": incoming,
        "auto_deduplicated_pct": round(100 * duplicate_reports / incoming, 1),
        "median_first_action_hours": round(median(action_hours), 1) if action_hours else None,
        "sla_breach_rate_pct": round(100 * breached / len(complaints), 1),
        "gps_precise_pct": round(100 * precise / len(complaints), 1),
    }


def community_priorities(complaints: list[Complaint], precision: int = 3) -> list[dict]:
    """Rank privacy-safe community issue groups by impact, never exact records."""
    rank = {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3, Priority.CRITICAL: 4}
    groups: dict[tuple[str, float, float], dict] = {}
    for complaint in complaints:
        key = (
            complaint.category.value,
            round(complaint.geo.lat, precision),
            round(complaint.geo.lng, precision),
        )
        reports = complaint.duplicate_reports_count + 1
        current = groups.setdefault(
            key,
            {
                "category": complaint.category.value,
                "area": f"{key[1]:.3f}, {key[2]:.3f} grid",
                "report_count": 0,
                "priority": complaint.priority.value,
                "open_count": 0,
            },
        )
        current["report_count"] += reports
        current["open_count"] += int(complaint.status != Status.RESOLVED)
        if rank[complaint.priority] > rank[Priority(current["priority"])]:
            current["priority"] = complaint.priority.value
    return sorted(
        (g for g in groups.values() if g["report_count"] >= K_ANONYMITY_THRESHOLD),
        key=lambda group: (rank[Priority(group["priority"])], group["report_count"]),
        reverse=True,
    )
