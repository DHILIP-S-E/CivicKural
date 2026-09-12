from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wardwatch.ids import new_complaint_id
from wardwatch.models import (
    Category,
    Complaint,
    Geo,
    GeoSource,
    Severity,
    Status,
    StatusEvent,
)


def make_complaint(
    *,
    lat: float = 9.9252,
    lng: float = 78.1198,
    category: Category = Category.POTHOLE,
    source: GeoSource = GeoSource.WHATSAPP_SHARE,
    status: Status = Status.OPEN,
    created_at: datetime | None = None,
    sla_deadline: datetime | None = None,
    ward_id: str = "MDU-W14",
    tenant_id: str = "MDU-CORP",
) -> Complaint:
    created_at = created_at or datetime.now(timezone.utc)
    return Complaint(
        complaint_id=new_complaint_id(created_at),
        tenant_id=tenant_id,
        ward_id=ward_id,
        citizen_phone_hash="a" * 64,
        category=category,
        severity=Severity.MEDIUM,
        geo=Geo(lat=lat, lng=lng, source=source),
        description="test",
        status=status,
        created_at=created_at,
        sla_deadline=sla_deadline or created_at + timedelta(days=7),
        status_history=[StatusEvent(status=Status.OPEN, ts=created_at)],
    )
