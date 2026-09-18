from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from model_config.config import get_settings
from model_config.errors import ServiceError

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]


def get_principal(credentials: BearerCredentials) -> Principal:
    if credentials is None:
        raise ServiceError(
            code="auth.missing",
            message="Bearer token is required",
            status_code=401,
        )
    settings = get_settings()
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
    return Principal(
        user_id=str(claims["sub"]),
        tenant_id=str(claims["tenant_id"]),
        roles=tuple(str(role) for role in claims["roles"]),
    )
