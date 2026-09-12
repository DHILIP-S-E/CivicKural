"""DedupAgent — pure function, no LLM (spec §3, §6)."""
from __future__ import annotations

from dataclasses import dataclass

from ..geo import dedup_radius_m, haversine_m, requires_merge_review
from ..models import Complaint, Geo


@dataclass
class DedupDecision:
    is_duplicate: bool
    match: Complaint | None = None
    needs_review: bool = False
    distance_m: float | None = None


def find_duplicate(new_geo: Geo, open_same_category: list[Complaint]) -> DedupDecision:
    """Return the nearest open complaint within the geo-source-adjusted radius.

    The radius is chosen from the *less* confident of the two location sources so
    an exact-GPS report and a described report are compared at the wider radius.
    """
    best: Complaint | None = None
    best_dist = float("inf")
    for c in open_same_category:
        radius = max(dedup_radius_m(new_geo.source), dedup_radius_m(c.geo.source))
        d = haversine_m(new_geo.lat, new_geo.lng, c.geo.lat, c.geo.lng)
        if d <= radius and d < best_dist:
            best, best_dist = c, d

    if best is None:
        return DedupDecision(is_duplicate=False)

    needs_review = requires_merge_review(new_geo.source) or requires_merge_review(best.geo.source)
    return DedupDecision(
        is_duplicate=True, match=best, needs_review=needs_review, distance_m=best_dist
    )
