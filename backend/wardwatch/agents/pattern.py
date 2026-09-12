"""PatternAgent — recurring-issue clustering + one summary call (spec §9).

Clustering is deterministic. The single model call only writes the human summary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..geo import PATTERN_RADIUS_M, haversine_m
from ..ids import new_flag_id
from ..llm import text
from ..models import Category, Complaint, Geo, GeoSource, InfraFlag

WINDOW_DAYS = 90
THRESHOLD = 3

SYSTEM_PROMPT = """You write one-sentence infrastructure findings for a city engineer.
Given a count of recurring complaints of one category at one location over 90 days,
state the likely root cause and recommend infrastructure review vs spot repair.
Reply with a single sentence, no preamble."""


@dataclass
class Cluster:
    category: Category
    members: list[Complaint] = field(default_factory=list)

    @property
    def centroid(self) -> Geo:
        n = len(self.members)
        return Geo(
            lat=sum(m.geo.lat for m in self.members) / n,
            lng=sum(m.geo.lng for m in self.members) / n,
            source=GeoSource.GEOCODED,
        )


def cluster(complaints: list[Complaint], now: datetime) -> list[Cluster]:
    cutoff = now - timedelta(days=WINDOW_DAYS)
    recent = [c for c in complaints if c.created_at >= cutoff]
    clusters: list[Cluster] = []
    for c in recent:
        placed = False
        for cl in clusters:
            if cl.category != c.category:
                continue
            if any(
                haversine_m(c.geo.lat, c.geo.lng, m.geo.lat, m.geo.lng) <= PATTERN_RADIUS_M
                for m in cl.members
            ):
                cl.members.append(c)
                placed = True
                break
        if not placed:
            clusters.append(Cluster(category=c.category, members=[c]))
    return [cl for cl in clusters if len(cl.members) >= THRESHOLD]


def summarize(cl: Cluster, summarizer=text) -> str:
    return summarizer(
        SYSTEM_PROMPT,
        f"{len(cl.members)} {cl.category.value} complaints within "
        f"{PATTERN_RADIUS_M}m over {WINDOW_DAYS} days.",
    ).strip()


def find_flags(
    tenant_id: str, ward_id: str, complaints: list[Complaint], now: datetime, summarizer=text
) -> list[InfraFlag]:
    flags: list[InfraFlag] = []
    for cl in cluster(complaints, now):
        flags.append(
            InfraFlag(
                flag_id=new_flag_id(),
                tenant_id=tenant_id,
                ward_id=ward_id,
                category=cl.category,
                centroid=cl.centroid,
                incident_count=len(cl.members),
                window_days=WINDOW_DAYS,
                summary=summarize(cl, summarizer),
            )
        )
    return flags
