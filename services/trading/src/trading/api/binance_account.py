from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from trading.api.dependencies import (
    RuntimeGuard,
    get_binance_client,
    get_binance_overview_cache,
    get_binance_runtime_manager,
    get_runtime_guard,
    get_secret_backend,
    require_binding_runtime,
)
from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionProbe
from trading.binance_account import (
    BinanceAccountReplaceCommand,
    BinanceAccountService,
    BinanceAccountView,
)
from trading.binance_runtime.overview import BinanceOverviewCache
from trading.binance_runtime.ports import RuntimeManager
from trading.db import get_session
from trading.errors import ServiceError
from trading.secrets import SecretBackend
from trading.security import Principal, get_principal, require_sensitive_write

router = APIRouter(prefix="/api/v1/trading/binance", tags=["binance-account"])


def get_binance_account_service(
    session: Annotated[Session, Depends(get_session)],
    secret_backend: Annotated[SecretBackend, Depends(get_secret_backend)],
    permission_probe: Annotated[AccountPermissionProbe, Depends(get_binance_client)],
    runtime_manager: Annotated[RuntimeManager, Depends(get_binance_runtime_manager)],
    overview_cache: Annotated[BinanceOverviewCache, Depends(get_binance_overview_cache)],
) -> BinanceAccountService:
    return BinanceAccountService(
        session,
        secret_backend,
        permission_probe,
        runtime_manager=runtime_manager,
        on_changed=overview_cache.invalidate,
    )


@router.get("/account", response_model=BinanceAccountView)
def get_binance_account(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[BinanceAccountService, Depends(get_binance_account_service)],
) -> BinanceAccountView:
    try:
        return service.get(principal.tenant_id)
    except LookupError as error:
        raise ServiceError(
            code="binance.account_missing",
            message=str(error),
            status_code=404,
        ) from error


@router.put("/account", response_model=BinanceAccountView)
async def replace_binance_account(
    payload: BinanceAccountReplaceCommand,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[BinanceAccountService, Depends(get_binance_account_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
) -> BinanceAccountView:
    require_sensitive_write(principal)
    require_binding_runtime(runtime)
    try:
        return await service.replace(
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            actor_roles=principal.roles,
            command=payload,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error
    except BinanceConnectorError as error:
        raise ServiceError(
            code=error.code,
            message=str(error),
            status_code=error.status_code or 409,
        ) from error
    except ValueError as error:
        raise ServiceError(
            code="binance.account_rejected",
            message=str(error),
            status_code=409,
        ) from error


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binance_account(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[BinanceAccountService, Depends(get_binance_account_service)],
) -> Response:
    require_sensitive_write(principal)
    try:
        await service.delete(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error
    except LookupError as error:
        raise ServiceError(
            code="binance.account_missing",
            message=str(error),
            status_code=404,
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["get_binance_account_service", "router"]
