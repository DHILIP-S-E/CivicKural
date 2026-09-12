"""Local dev helpers: mint tokens and seed sample complaints.

Usage:
    python -m wardwatch.devtools token officer MDU-W14
    python -m wardwatch.devtools seed
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from . import db
from .api.auth import issue_token
from .config import get_settings
from .ids import new_complaint_id
from .models import (
    Category,
    Complaint,
    Dept,
    Geo,
    GeoSource,
    Severity,
    Status,
    StatusEvent,
)
from .sla import sla_deadline


def _token(argv: list[str]) -> None:
    role = argv[0] if argv else "officer"
    wards = argv[1:] or ["MDU-W14"]
    print(issue_token(f"{role}-dev", role, get_settings().default_tenant_id, wards))


def _seed(_: list[str]) -> None:
    tenant = get_settings().default_tenant_id
    now = datetime.now(timezone.utc)
    samples = [
        (Category.POTHOLE, Dept.ROADS, 9.9252, 78.1198, 0),
        (Category.WATER_LEAK, Dept.WATER_BOARD, 9.9260, 78.1205, 3),
        (Category.GARBAGE, Dept.SANITATION, 9.9241, 78.1189, 5),
        (Category.STREETLIGHT, Dept.ELECTRICAL, 9.9255, 78.1210, 1),
    ]
    for cat, dept, lat, lng, age_days in samples:
        created = now - timedelta(days=age_days)
        cid = new_complaint_id(created)
        db.put_complaint(
            Complaint(
                complaint_id=cid,
                tenant_id=tenant,
                ward_id="MDU-W14",
                citizen_phone_hash="0" * 64,
                category=cat,
                severity=Severity.MEDIUM,
                geo=Geo(lat=lat, lng=lng, source=GeoSource.WHATSAPP_SHARE),
                description=f"Sample {cat.value} report",
                status=Status.OPEN,
                created_at=created,
                sla_deadline=sla_deadline(cat, created),
                routed_dept=dept,
                status_history=[StatusEvent(status=Status.OPEN, ts=created)],
            )
        )
        print("seeded", cid, cat.value)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    {"token": _token, "seed": _seed}[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
