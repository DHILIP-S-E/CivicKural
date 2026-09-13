"""Admin-only settings routes (spec §5) — routing rules, SLA durations, dept contacts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import db
from ..models import NotifyOutcome, TenantConfig
from ..wards import TENANT_WARDS, wards_for
from .auth import Principal, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=TenantConfig)
def get_settings_route(p: Principal = Depends(require_admin)) -> TenantConfig:
    return db.get_tenant_config(p.tenant_id)


class AdminHealth(BaseModel):
    last_escalation_sweep_at: datetime | None
    last_pattern_sweep_at: datetime | None
    recent_notification_failures: int


@router.get("/health", response_model=AdminHealth)
def get_admin_health(
    p: Principal = Depends(require_admin), lookback_hours: int = 24
) -> AdminHealth:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    failures = 0
    for tenant_id in TENANT_WARDS:
        for ward_id in wards_for(tenant_id):
            for complaint in db.query_ward(tenant_id, ward_id):
                for attempt in complaint.citizen_notify_log:
                    if attempt.outcome == NotifyOutcome.FAILED and attempt.ts >= since:
                        failures += 1
    return AdminHealth(
        last_escalation_sweep_at=db.get_sweep_marker("escalation"),
        last_pattern_sweep_at=db.get_sweep_marker("pattern"),
        recent_notification_failures=failures,
    )


@router.put("/settings", response_model=TenantConfig)
def put_settings_route(
    cfg: TenantConfig, p: Principal = Depends(require_admin)
) -> TenantConfig:
    cfg.tenant_id = p.tenant_id
    db.put_tenant_config(cfg)
    return cfg
