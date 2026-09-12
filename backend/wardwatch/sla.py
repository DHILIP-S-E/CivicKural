"""SLA duration table and deadline calculation (spec §6)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import Category, TenantConfig

# Default SLA durations in days, per category.
DEFAULT_SLA_DAYS: dict[Category, int] = {
    Category.WATER_LEAK: 1,
    Category.GARBAGE: 2,
    Category.STREETLIGHT: 5,
    Category.POTHOLE: 7,
    Category.OTHER: 5,
}


def sla_days(category: Category, config: TenantConfig | None = None) -> int:
    if config and category.value in config.sla_overrides:
        return int(config.sla_overrides[category.value])
    return DEFAULT_SLA_DAYS[category]


def sla_deadline(
    category: Category, created_at: datetime, config: TenantConfig | None = None
) -> datetime:
    return created_at + timedelta(days=sla_days(category, config))
