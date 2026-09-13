"""JWT verification + role / ward-scope gates (spec §4, §5).

Backend-enforced: an officer token cannot reach admin routes even by calling the
API directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings

_bearer = HTTPBearer(auto_error=True)


@dataclass
class Principal:
    sub: str
    role: str  # "officer" | "admin" | "coordinator"
    tenant_id: str
    wards: list[str]

    def can_see_ward(self, ward_id: str) -> bool:
        return self.role == "admin" or ward_id in self.wards


def issue_token(sub: str, role: str, tenant_id: str, wards: list[str]) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": sub,
            "role": role,
            "tenant_id": tenant_id,
            "wards": wards,
            "iat": now,
            "exp": now + timedelta(minutes=s.jwt_expires_minutes),
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )


def current_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Principal:
    s = get_settings()
    if s.cognito_user_pool_id and s.cognito_client_id:
        try:
            response = boto3.client("cognito-idp", region_name=s.aws_region).get_user(
                AccessToken=creds.credentials
            )
            attributes = {
                item["Name"]: item["Value"] for item in response.get("UserAttributes", [])
            }
            role = attributes.get("custom:role", "officer")
            tenant_id = attributes.get("custom:tenant_id", s.default_tenant_id)
            wards = [
                ward.strip()
                for ward in attributes.get("custom:wards", "").split(",")
                if ward.strip()
            ]
            if role not in {"admin", "officer", "coordinator"}:
                raise ValueError("invalid role")
            return Principal(
                sub=attributes.get("sub", response.get("Username", "")),
                role=role,
                tenant_id=tenant_id,
                wards=wards,
            )
        except (BotoCoreError, ClientError, KeyError, ValueError):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired session")
    try:
        claims = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
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


def require_operator(p: Principal = Depends(current_principal)) -> Principal:
    if p.role not in {"officer", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "officer or admin role required")
    return p
