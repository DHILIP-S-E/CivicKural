"""Admin-only settings routes (spec §5) — routing rules, SLA durations, dept contacts."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import db
from ..models import TenantConfig
from .auth import Principal, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings", response_model=TenantConfig)
def get_settings_route(p: Principal = Depends(require_admin)) -> TenantConfig:
    return db.get_tenant_config(p.tenant_id)


@router.put("/settings", response_model=TenantConfig)
def put_settings_route(
    cfg: TenantConfig, p: Principal = Depends(require_admin)
) -> TenantConfig:
    cfg.tenant_id = p.tenant_id
    db.put_tenant_config(cfg)
    return cfg
