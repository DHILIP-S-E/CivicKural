from datetime import datetime, timezone

from wardwatch.models import Category, TenantConfig
from wardwatch.sla import sla_days, sla_deadline


def test_defaults():
    assert sla_days(Category.WATER_LEAK) == 1
    assert sla_days(Category.GARBAGE) == 2
    assert sla_days(Category.STREETLIGHT) == 5
    assert sla_days(Category.POTHOLE) == 7
    assert sla_days(Category.OTHER) == 5


def test_tenant_override():
    cfg = TenantConfig(tenant_id="T", sla_overrides={"pothole": 3})
    assert sla_days(Category.POTHOLE, cfg) == 3


def test_deadline():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert sla_deadline(Category.WATER_LEAK, now).day == 11
