import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from risk.config import get_settings
from risk.errors import ServiceError


@dataclass(frozen=True)
class ServiceIdentity:
    name: str


def require_service_identity(
    service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> ServiceIdentity:
    expected = get_settings().service_token
    if service_token is None:
        raise ServiceError(
            code="auth.service_token_missing",
            message="Service token is required",
            status_code=401,
        )
    if expected is None or not hmac.compare_digest(
        service_token,
        expected.get_secret_value(),
    ):
        raise ServiceError(
            code="auth.service_token_invalid",
            message="Service token is invalid",
            status_code=401,
        )
    return ServiceIdentity(name="trading")
