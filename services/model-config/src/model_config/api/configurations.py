from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from model_config.config import get_settings
from model_config.db import get_session
from model_config.errors import ServiceError
from model_config.secrets import LocalEncryptedSecretBackend
from model_config.security import Principal, get_principal
from model_config.service import (
    ConfigurationCreate,
    ConfigurationInUseError,
    ConfigurationNotFoundError,
    ConfigurationView,
    ModelConfigurationService,
    PlannedProviderError,
)

router = APIRouter(prefix="/api/v1/tenant/model-configurations", tags=["model-config"])


@lru_cache
def get_secret_backend() -> LocalEncryptedSecretBackend:
    key = get_settings().secret_encryption_key.get_secret_value()
    return LocalEncryptedSecretBackend(key)


def get_configuration_service(
    session: Annotated[Session, Depends(get_session)],
) -> Iterator[ModelConfigurationService]:
    yield ModelConfigurationService(session, get_secret_backend())


@router.get("", response_model=list[ConfigurationView])
def list_configurations(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ModelConfigurationService, Depends(get_configuration_service)],
) -> list[ConfigurationView]:
    return service.list_for_tenant(principal.tenant_id)


@router.post("", response_model=ConfigurationView, status_code=status.HTTP_201_CREATED)
def create_configuration(
    payload: ConfigurationCreate,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ModelConfigurationService, Depends(get_configuration_service)],
) -> ConfigurationView:
    try:
        return service.create(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            command=payload,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error


@router.post("/{configuration_id}/test")
def test_configuration(
    configuration_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ModelConfigurationService, Depends(get_configuration_service)],
) -> dict[str, bool]:
    def probe(url: str, secret: str) -> bool:
        response = httpx.get(
            f"{url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {secret}"},
            follow_redirects=False,
            timeout=5,
        )
        return response.status_code < 500

    try:
        result = service.test_connection(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            configuration_id=configuration_id,
            connector=probe,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error
    except PlannedProviderError as error:
        raise ServiceError(
            code="model.provider_planned",
            message=str(error),
            status_code=409,
        ) from error
    except ConfigurationNotFoundError as error:
        raise ServiceError(
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error
    return {"connected": result}


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration(
    configuration_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ModelConfigurationService, Depends(get_configuration_service)],
) -> None:
    try:
        service.delete(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            configuration_id=configuration_id,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error
    except ConfigurationInUseError as error:
        raise ServiceError(
            code="model.configuration_in_use",
            message=str(error),
            status_code=409,
        ) from error
    except ConfigurationNotFoundError as error:
        raise ServiceError(
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error
