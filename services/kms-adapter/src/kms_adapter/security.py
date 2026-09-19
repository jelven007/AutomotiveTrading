import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from kms_adapter.config import get_settings
from kms_adapter.errors import ServiceError


@dataclass(frozen=True)
class ServiceIdentity:
    name: str


def require_service_identity(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ServiceIdentity:
    if authorization is None:
        raise ServiceError(
            code="auth.service_token_missing",
            message="Service token is required",
            status_code=401,
        )
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        raise ServiceError(
            code="auth.service_token_invalid",
            message="Service token is invalid",
            status_code=401,
        )
    expected = get_settings().service_token
    if expected is None or not hmac.compare_digest(token, expected.get_secret_value()):
        raise ServiceError(
            code="auth.service_token_invalid",
            message="Service token is invalid",
            status_code=401,
        )
    return ServiceIdentity(name="trading")
