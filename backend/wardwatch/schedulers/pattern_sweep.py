"""EventBridge target — pattern sweep, weekly (spec §9)."""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..agents import pattern
from ..wards import TENANT_WARDS, wards_for


def run_sweep(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    flags_written = 0
    for tenant_id in TENANT_WARDS:
        for ward_id in wards_for(tenant_id):
            complaints = db.query_ward(tenant_id, ward_id)
            existing = {f.flag_id for f in db.query_infra_flags(tenant_id, ward_id)}
            for flag in pattern.find_flags(
                tenant_id, ward_id, complaints, now, existing_flag_ids=existing
            ):
                db.put_infra_flag(flag)
                flags_written += 1
    db.put_sweep_marker("pattern", now)
    return {"infra_flags": flags_written}


def handler(event, context):
    return run_sweep()
