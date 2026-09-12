from wardwatch.agents.routing import route
from wardwatch.models import Category, Dept, TenantConfig


def test_rule_table():
    assert route(Category.POTHOLE) == Dept.ROADS
    assert route(Category.GARBAGE) == Dept.SANITATION
    assert route(Category.WATER_LEAK) == Dept.WATER_BOARD
    assert route(Category.STREETLIGHT) == Dept.ELECTRICAL


def test_other_without_fallback_is_unassigned():
    assert route(Category.OTHER, "fallen tree") == Dept.UNASSIGNED


def test_other_uses_llm_fallback():
    assert route(Category.OTHER, "fallen tree branch", llm_fallback=lambda d: "sanitation") == Dept.SANITATION


def test_tenant_override_wins():
    cfg = TenantConfig(tenant_id="T", routing_overrides={"pothole": "sanitation"})
    assert route(Category.POTHOLE, config=cfg) == Dept.SANITATION
