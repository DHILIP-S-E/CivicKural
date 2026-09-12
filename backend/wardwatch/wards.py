"""Static tenant -> ward roster (a real deployment would store this in DynamoDB)."""
from __future__ import annotations

TENANT_WARDS: dict[str, list[str]] = {
    "MDU-CORP": ["MDU-W14"],
}


def wards_for(tenant_id: str) -> list[str]:
    return TENANT_WARDS.get(tenant_id, [])
