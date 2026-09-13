"""DynamoDB repository (spec §7).

Single-table design:
  PK  = tenant_id#ward_id
  SK  = item id  (WM-... for complaints, INFRA#... for flags, CONFIG for tenant config)

GSI1: gsi1pk = tenant_id#ward_id#category, gsi1sk = status   -> open-complaint dedup query
GSI2: gsi2pk = tenant_id,                  gsi2sk = sla_deadline -> escalation sweep
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

import boto3
from boto3.dynamodb.conditions import Key

from .config import get_settings
from .models import (
    Complaint,
    InfraFlag,
    InboundSession,
    OPEN_STATUSES,
    Status,
    TenantConfig,
)

CONFIG_SK = "CONFIG"
SESSION_SK = "ACTIVE"
SYSTEM_PK = "SYSTEM"


def _table():
    s = get_settings()
    return boto3.resource("dynamodb", region_name=s.aws_region).Table(s.wardwatch_table)


def _dumps(model) -> dict[str, Any]:
    # Round-trip through JSON so datetimes/enums become plain strings, and floats
    # become Decimal (DynamoDB rejects float).
    return json.loads(model.model_dump_json(), parse_float=Decimal)


def _complaint_item(c: Complaint) -> dict[str, Any]:
    item = _dumps(c)
    item["pk"] = c.pk
    item["sk"] = c.complaint_id
    item["gsi1pk"] = f"{c.tenant_id}#{c.ward_id}#{c.category.value}"
    item["gsi1sk"] = c.status.value
    item["gsi2pk"] = c.tenant_id
    item["gsi2sk"] = c.sla_deadline.isoformat()
    item["item_type"] = "COMPLAINT"
    return item


def put_complaint(c: Complaint) -> None:
    _table().put_item(Item=_complaint_item(c))


def get_complaint(tenant_id: str, ward_id: str, complaint_id: str) -> Complaint | None:
    resp = _table().get_item(Key={"pk": f"{tenant_id}#{ward_id}", "sk": complaint_id})
    item = resp.get("Item")
    return _to_complaint(item) if item else None


def _to_complaint(item: dict[str, Any]) -> Complaint:
    fields = {k: v for k, v in item.items() if k in Complaint.model_fields}
    return Complaint.model_validate(fields)


def open_complaints_by_category(
    tenant_id: str, ward_id: str, category: str
) -> list[Complaint]:
    resp = _table().query(
        IndexName="gsi1",
        KeyConditionExpression=Key("gsi1pk").eq(f"{tenant_id}#{ward_id}#{category}"),
    )
    out = [_to_complaint(i) for i in resp.get("Items", [])]
    return [c for c in out if c.status in OPEN_STATUSES]


def complaints_past_deadline(tenant_id: str, now: datetime) -> list[Complaint]:
    resp = _table().query(
        IndexName="gsi2",
        KeyConditionExpression=Key("gsi2pk").eq(tenant_id)
        & Key("gsi2sk").lte(now.isoformat()),
    )
    out = [_to_complaint(i) for i in resp.get("Items", []) if i.get("item_type") == "COMPLAINT"]
    return [c for c in out if c.status in OPEN_STATUSES]


def query_ward(tenant_id: str, ward_id: str) -> list[Complaint]:
    resp = _table().query(
        KeyConditionExpression=Key("pk").eq(f"{tenant_id}#{ward_id}")
        & Key("sk").begins_with("WM-")
    )
    return [_to_complaint(i) for i in resp.get("Items", [])]


def query_tenant_complaints(tenant_id: str, ward_ids: Iterable[str]) -> list[Complaint]:
    out: list[Complaint] = []
    for w in ward_ids:
        out.extend(query_ward(tenant_id, w))
    return out


# --- infra flags ---
def put_infra_flag(f: InfraFlag) -> None:
    item = _dumps(f)
    item["pk"] = f"{f.tenant_id}#{f.ward_id}"
    item["sk"] = f"INFRA#{f.flag_id}"
    item["item_type"] = "INFRA_FLAG"
    _table().put_item(Item=item)


def query_infra_flags(tenant_id: str, ward_id: str) -> list[InfraFlag]:
    resp = _table().query(
        KeyConditionExpression=Key("pk").eq(f"{tenant_id}#{ward_id}")
        & Key("sk").begins_with("INFRA#")
    )
    return [
        InfraFlag.model_validate({k: v for k, v in i.items() if k in InfraFlag.model_fields})
        for i in resp.get("Items", [])
    ]


# --- tenant config ---
def get_tenant_config(tenant_id: str) -> TenantConfig:
    # Config lives under a sentinel ward so a single get works.
    resp = _table().get_item(Key={"pk": f"{tenant_id}#_", "sk": CONFIG_SK})
    item = resp.get("Item")
    if not item:
        return TenantConfig(tenant_id=tenant_id)
    return TenantConfig.model_validate(
        {k: v for k, v in item.items() if k in TenantConfig.model_fields}
    )


def put_tenant_config(cfg: TenantConfig) -> None:
    item = _dumps(cfg)
    item["pk"] = f"{cfg.tenant_id}#_"
    item["sk"] = CONFIG_SK
    item["item_type"] = "CONFIG"
    _table().put_item(Item=item)


# --- short-lived WhatsApp conversation assembly (DynamoDB TTL compatible) ---
def get_inbound_session(tenant_id: str, phone_hash: str) -> InboundSession | None:
    response = _table().get_item(
        Key={"pk": f"SESSION#{tenant_id}#{phone_hash}", "sk": SESSION_SK}
    )
    item = response.get("Item")
    if not item:
        return None
    return InboundSession.model_validate(
        {key: value for key, value in item.items() if key in InboundSession.model_fields}
    )


def put_inbound_session(session: InboundSession) -> None:
    item = _dumps(session)
    item.update({
        "pk": f"SESSION#{session.tenant_id}#{session.citizen_phone_hash}",
        "sk": SESSION_SK,
        "item_type": "INBOUND_SESSION",
    })
    _table().put_item(Item=item)


def delete_inbound_session(tenant_id: str, phone_hash: str) -> None:
    _table().delete_item(Key={"pk": f"SESSION#{tenant_id}#{phone_hash}", "sk": SESSION_SK})


# --- sweep run markers (spec §7 admin health) ---
def put_sweep_marker(name: str, ts: datetime) -> None:
    """Record the last time a scheduled sweep (e.g. "escalation", "pattern") ran."""
    _table().put_item(
        Item={
            "pk": SYSTEM_PK,
            "sk": f"SWEEP#{name}",
            "item_type": "SWEEP_MARKER",
            "last_run": ts.isoformat(),
        }
    )


def get_sweep_marker(name: str) -> datetime | None:
    resp = _table().get_item(Key={"pk": SYSTEM_PK, "sk": f"SWEEP#{name}"})
    item = resp.get("Item")
    if not item:
        return None
    return datetime.fromisoformat(item["last_run"])
