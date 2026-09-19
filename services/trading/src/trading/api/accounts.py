from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError

from trading.accounts import (
    AccountBindCommand,
    TradingAccountService,
    TradingAccountView,
)
from trading.api.dependencies import (
    RuntimeGuard,
    get_account_service,
    get_runtime_guard,
    require_binding_runtime,
    require_live_runtime,
)
from trading.binance.errors import BinanceConnectorError
from trading.errors import ServiceError
from trading.models import MarketGroup
from trading.security import Principal, get_principal

router = APIRouter(prefix="/api/v1/trading/accounts", tags=["trading-accounts"])


@router.get("", response_model=list[TradingAccountView])
def list_accounts(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[TradingAccountService, Depends(get_account_service)],
) -> list[TradingAccountView]:
    return service.list_for_tenant(principal.tenant_id)


@router.post(
    "/bind",
    response_model=TradingAccountView,
    status_code=status.HTTP_201_CREATED,
)
def bind_account(
    payload: AccountBindCommand,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[TradingAccountService, Depends(get_account_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
) -> TradingAccountView:
    if payload.market_group is MarketGroup.BINANCE:
        require_binding_runtime(runtime)
    try:
        return service.bind(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
            command=payload,
            actor_user_id=principal.user_id,
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
            status_code=409,
        ) from error
    except IntegrityError as error:
        raise ServiceError(
            code="trading.account_conflict",
            message="Trading account alias already exists",
            status_code=409,
        ) from error
    except ValueError as error:
        raise ServiceError(
            code="trading.account_rejected",
            message=str(error),
            status_code=409,
        ) from error


@router.post("/{account_id}/enable-trading", response_model=TradingAccountView)
def enable_trading(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[TradingAccountService, Depends(get_account_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
) -> TradingAccountView:
    require_live_runtime(runtime)
    try:
        return service.enable_trading(
            tenant_id=principal.tenant_id,
            account_id=account_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
        )
    except PermissionError as error:
        raise ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        ) from error
    except LookupError as error:
        raise ServiceError(
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error
    except ValueError as error:
        raise ServiceError(
            code="trading.account_rejected",
            message=str(error),
            status_code=409,
        ) from error


@router.post("/{account_id}/test", response_model=TradingAccountView)
@router.post("/{account_id}/connect", response_model=TradingAccountView)
def test_or_connect_account(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[TradingAccountService, Depends(get_account_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
) -> TradingAccountView:
    require_binding_runtime(runtime)
    try:
        return service.test_connection(
            tenant_id=principal.tenant_id,
            account_id=account_id,
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
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error
    except (ValueError, BinanceConnectorError) as error:
        code = (
            error.code if isinstance(error, BinanceConnectorError) else "trading.account_rejected"
        )
        raise ServiceError(
            code=code,
            message=str(error),
            status_code=409,
        ) from error


@router.post("/{account_id}/disconnect", response_model=TradingAccountView)
def disconnect_account(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[TradingAccountService, Depends(get_account_service)],
) -> TradingAccountView:
    try:
        return service.disconnect(
            tenant_id=principal.tenant_id,
            account_id=account_id,
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
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error
