from functools import lru_cache
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from kms_adapter.config import get_settings
from kms_adapter.db import get_session
from kms_adapter.errors import ServiceError
from kms_adapter.provider import KmsProvider
from kms_adapter.security import require_service_identity
from kms_adapter.service import (
    EnvelopeSecretService,
    SecretIntegrityError,
    SecretNotFoundError,
    SecretPersistenceError,
    SecretUnavailableError,
)
from kms_adapter.volcengine_provider import VolcengineKmsProvider

TenantId = Annotated[
    str,
    Field(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"),
]

router = APIRouter(
    prefix="/v1/secrets",
    tags=["secrets"],
    dependencies=[Depends(require_service_identity)],
)


class SecretCreateRequest(BaseModel):
    tenant_id: TenantId
    value: dict[str, str] = Field(min_length=1, max_length=64)

    @field_validator("value")
    @classmethod
    def validate_secret_size(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or len(key) > 128 for key in value):
            raise ValueError("secret keys must contain between 1 and 128 characters")
        if sum(len(item.encode()) for item in value.values()) > 64 * 1024:
            raise ValueError("secret value exceeds the size limit")
        return value


class SecretReferenceRequest(BaseModel):
    tenant_id: TenantId
    secret_ref: str = Field(min_length=1, max_length=256)


class SecretCreateResponse(BaseModel):
    secret_ref: str


class SecretResolveResponse(BaseModel):
    value: dict[str, str]


@lru_cache
def get_kms_provider() -> KmsProvider:
    settings = get_settings()
    return VolcengineKmsProvider(
        access_key=(
            settings.volcengine_access_key.get_secret_value()
            if settings.volcengine_access_key
            else None
        ),
        secret_key=(
            settings.volcengine_secret_key.get_secret_value()
            if settings.volcengine_secret_key
            else None
        ),
        session_token=(
            settings.volcengine_session_token.get_secret_value()
            if settings.volcengine_session_token
            else None
        ),
        region=settings.kms_region,
    )


def get_envelope_service(
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[KmsProvider, Depends(get_kms_provider)],
) -> EnvelopeSecretService:
    settings = get_settings()
    if not settings.kms_key_id:
        raise ServiceError(
            code="kms.configuration_invalid",
            message="KMS adapter is not configured",
            status_code=503,
        )
    return EnvelopeSecretService(
        session,
        provider,
        key_id=settings.kms_key_id,
        purpose=settings.secret_purpose,
    )


@router.post("", response_model=SecretCreateResponse, status_code=status.HTTP_201_CREATED)
def create_secret(
    payload: SecretCreateRequest,
    service: Annotated[EnvelopeSecretService, Depends(get_envelope_service)],
) -> SecretCreateResponse:
    try:
        secret_ref = service.put(payload.tenant_id, payload.value)
    except (SecretPersistenceError, SecretUnavailableError) as error:
        _raise_service_error(error)
    return SecretCreateResponse(secret_ref=secret_ref)


@router.post("/resolve", response_model=SecretResolveResponse)
def resolve_secret(
    payload: SecretReferenceRequest,
    service: Annotated[EnvelopeSecretService, Depends(get_envelope_service)],
) -> SecretResolveResponse:
    try:
        value = service.resolve(payload.tenant_id, payload.secret_ref)
    except (
        SecretIntegrityError,
        SecretNotFoundError,
        SecretUnavailableError,
    ) as error:
        _raise_service_error(error)
    return SecretResolveResponse(value=value)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(
    payload: SecretReferenceRequest,
    service: Annotated[EnvelopeSecretService, Depends(get_envelope_service)],
) -> Response:
    try:
        service.delete(payload.tenant_id, payload.secret_ref)
    except (
        SecretNotFoundError,
        SecretPersistenceError,
    ) as error:
        _raise_service_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _raise_service_error(error: Exception) -> NoReturn:
    if isinstance(error, SecretNotFoundError):
        raise ServiceError(
            code="kms.secret_not_found",
            message="Secret reference does not exist",
            status_code=404,
        ) from error
    if isinstance(error, SecretIntegrityError):
        raise ServiceError(
            code="kms.secret_integrity_failed",
            message="Secret cannot be resolved",
            status_code=503,
        ) from error
    raise ServiceError(
        code="kms.unavailable",
        message="KMS adapter is unavailable",
        status_code=503,
    ) from error
