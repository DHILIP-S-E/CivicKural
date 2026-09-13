"""Transparent, configurable priority assessment for CivicFix reports."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Category, Priority, Severity, TenantConfig

DEFAULT_WEIGHTS = {
    "severity": 2,
    "safety": 2,
    "sensitive_location": 1,
    "community_reports": 1,
    "duration": 1,
    "people_affected": 1,
    "evidence": 1,
}


@dataclass(frozen=True)
class PriorityAssessment:
    priority: Priority
    score: int
    factors: dict[str, int]


def assess(
    category: Category,
    severity: Severity,
    description: str,
    report_count: int = 1,
    config: TenantConfig | None = None,
    evidence_relevant: bool | None = None,
) -> PriorityAssessment:
    weights = DEFAULT_WEIGHTS | ((config.priority_weights or {}) if config else {})
    text = description.casefold()
    safety_terms = ("danger", "accident", "blocking", "injury", "fell", "flood", "live wire")
    location_terms = ("school", "hospital", "crossing", "market", "bus stand")
    duration_terms = ("days", "week", "weeks", "month", "months", "நாள்", "வாரம்")
    people_terms = ("people", "residents", "traffic", "children", "pedestrian", "மக்கள்")
    factors = {
        "severity": {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}[severity],
        "safety": 1 if any(term in text for term in safety_terms) else 0,
        "sensitive_location": 1 if any(term in text for term in location_terms) else 0,
        "community_reports": 2 if report_count >= 10 else 1 if report_count >= 3 else 0,
        "duration": 1 if any(term in text for term in duration_terms) else 0,
        "people_affected": 1 if any(term in text for term in people_terms) else 0,
        "evidence": 1 if evidence_relevant is True else 0,
    }
    # Water leaks are time-sensitive even when the wording is understated.
    if category == Category.WATER_LEAK:
        factors["safety"] = max(factors["safety"], 1)
    score = sum(factors[name] * int(weights.get(name, 1)) for name in factors)
    priority = (
        Priority.CRITICAL if score >= 10 else
        Priority.HIGH if score >= 7 else
        Priority.MEDIUM if score >= 4 else
        Priority.LOW
    )
    return PriorityAssessment(priority=priority, score=score, factors=factors)
