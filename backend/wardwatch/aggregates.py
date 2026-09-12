"""Department-level SLA compliance + hotspot density (spec §5, §10).

Every value here is ward-level or coarser. No individual-complaint field is exposed.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Complaint, Status


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
    return {
        dept: {
            "resolved_within_sla_pct": round(100 * w / total) if total else None,
            "resolved_count": total,
        }
        for dept, (w, total) in tally.items()
    }


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


def hotspot_density(complaints: list[Complaint], precision: int = 3) -> list[dict]:
    """Grid-binned counts only — coordinates rounded so nothing pinpoints an address."""
    bins: dict[tuple[float, float], int] = defaultdict(int)
    for c in complaints:
        key = (round(c.geo.lat, precision), round(c.geo.lng, precision))
        bins[key] += 1
    return [{"lat": k[0], "lng": k[1], "count": v} for k, v in bins.items()]
