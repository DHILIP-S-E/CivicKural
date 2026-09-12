"""RoutingAgent — rule table, rare LLM fallback for `other` (spec §4)."""
from __future__ import annotations

from ..models import Category, Dept, TenantConfig

ROUTING_TABLE: dict[Category, Dept] = {
    Category.POTHOLE: Dept.ROADS,
    Category.GARBAGE: Dept.SANITATION,
    Category.WATER_LEAK: Dept.WATER_BOARD,
    Category.STREETLIGHT: Dept.ELECTRICAL,
}


def route(
    category: Category,
    description: str = "",
    config: TenantConfig | None = None,
    llm_fallback=None,
) -> Dept:
    if config and category.value in config.routing_overrides:
        return Dept(config.routing_overrides[category.value])

    if category in ROUTING_TABLE:
        return ROUTING_TABLE[category]

    # category == other: only here do we (optionally) ask a model.
    if llm_fallback is not None:
        try:
            return Dept(llm_fallback(description))
        except (ValueError, Exception):  # noqa: BLE001 - fall through to unassigned
            pass
    return Dept.UNASSIGNED
