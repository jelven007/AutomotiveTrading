from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from trading.config import get_settings
from trading.errors import ServiceError

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]
    mfa_verified_at: datetime | None


def get_principal(credentials: BearerCredentials) -> Principal:
    if credentials is None:
        raise ServiceError(
            code="auth.missing",
            message="Bearer token is required",
            status_code=401,
        )
    settings = get_settings()
    if settings.auth_jwt_secret is None:
        raise ServiceError(
            code="auth.unavailable",
            message="Authentication is not configured",
            status_code=503,
        )
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            options={"require": ["iss", "aud", "sub", "tenant_id", "roles", "exp", "iat"]},
        )
    except InvalidTokenError as error:
        raise ServiceError(
            code="auth.invalid",
            message="Access token is invalid",
            status_code=401,
        ) from error

    mfa_time = claims.get("mfa_time")
    return Principal(
        user_id=str(claims["sub"]),
        tenant_id=str(claims["tenant_id"]),
        roles=tuple(str(role) for role in claims["roles"]),
        mfa_verified_at=(
            datetime.fromtimestamp(int(mfa_time), tz=UTC) if mfa_time is not None else None
        ),
    )


def require_recent_mfa(principal: Principal) -> None:
    max_age = timedelta(seconds=get_settings().mfa_max_age_seconds)
    if principal.mfa_verified_at is None or datetime.now(UTC) - principal.mfa_verified_at > max_age:
        raise ServiceError(
            code="auth.mfa_required",
            message="Recent MFA verification is required",
            status_code=403,
        )


def require_sensitive_write(principal: Principal) -> None:
    require_recent_mfa(principal)


def require_demo_trading_write(principal: Principal) -> None:
    if not get_settings().demo_trading_enabled:
        raise ServiceError(
            code="trading.demo_disabled",
            message="Demo trading is disabled",
            status_code=409,
        )
    require_sensitive_write(principal)


__all__ = [
    "Principal",
    "get_principal",
    "require_demo_trading_write",
    "require_recent_mfa",
    "require_sensitive_write",
]
