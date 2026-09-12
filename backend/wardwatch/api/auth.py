"""JWT verification + role / ward-scope gates (spec §4, §5).

Backend-enforced: an officer token cannot reach admin routes even by calling the
API directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings

_bearer = HTTPBearer(auto_error=True)


@dataclass
class Principal:
    sub: str
    role: str  # "officer" | "admin"
    tenant_id: str
    wards: list[str]

    def can_see_ward(self, ward_id: str) -> bool:
        return self.role == "admin" or ward_id in self.wards


def issue_token(sub: str, role: str, tenant_id: str, wards: list[str]) -> str:
    s = get_settings()
    return jwt.encode(
        {"sub": sub, "role": role, "tenant_id": tenant_id, "wards": wards},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )


def current_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Principal:
    s = get_settings()
    try:
        claims = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return Principal(
        sub=claims["sub"],
        role=claims.get("role", "officer"),
        tenant_id=claims["tenant_id"],
        wards=claims.get("wards", []),
    )


def require_admin(p: Principal = Depends(current_principal)) -> Principal:
    if p.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin role required")
    return p
