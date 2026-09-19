from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, Field

from trading.account_operations import (
    AccountOperationsService,
    AccountSnapshotView,
    FuturesLeverageCommand,
    MarginTransactionCommand,
    TradingOperationView,
)
from trading.api.dependencies import (
    RuntimeGuard,
    get_account_operations_service,
    get_runtime_guard,
    require_connector_runtime,
    require_live_runtime,
)
from trading.binance.errors import BinanceConnectorError
from trading.errors import ServiceError
from trading.models import AccountScopeType
from trading.orders import IdempotencyConflictError, TradingGuardError
from trading.security import Principal, get_principal

router = APIRouter(prefix="/api/v1/trading/accounts", tags=["trading-operations"])


class MarginTransactionPayload(BaseModel):
    account_scope: AccountScopeType
    symbol: str | None = Field(default=None, max_length=40)
    asset: str = Field(min_length=2, max_length=20)
    amount: Decimal = Field(gt=0)


class FuturesLeveragePayload(BaseModel):
    symbol: str = Field(min_length=3, max_length=40)
    leverage: int = Field(ge=1, le=125)


@router.get("/{account_id}/balances", response_model=AccountSnapshotView)
def get_balances(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    account_scope: Annotated[AccountScopeType, Query(alias="scope")] = AccountScopeType.SPOT,
    symbol: str | None = None,
) -> AccountSnapshotView:
    require_connector_runtime(runtime)
    try:
        return service.snapshot(
            tenant_id=principal.tenant_id,
            account_id=account_id,
            scope=account_scope,
            symbol=symbol,
        )
    except (LookupError, TradingGuardError, BinanceConnectorError, ValueError) as error:
        raise _operation_error(error) from error


@router.get("/{account_id}/margin-risk", response_model=AccountSnapshotView)
def get_margin_risk(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    account_scope: Annotated[AccountScopeType, Query(alias="scope")],
    symbol: str | None = None,
) -> AccountSnapshotView:
    if account_scope not in {
        AccountScopeType.CROSS_MARGIN,
        AccountScopeType.ISOLATED_MARGIN,
    }:
        raise ServiceError(
            code="trading.scope_invalid",
            message="Margin risk requires cross or isolated margin scope",
            status_code=422,
        )
    require_connector_runtime(runtime)
    try:
        return service.snapshot(
            tenant_id=principal.tenant_id,
            account_id=account_id,
            scope=account_scope,
            symbol=symbol,
        )
    except (LookupError, TradingGuardError, BinanceConnectorError, ValueError) as error:
        raise _operation_error(error) from error


@router.get("/{account_id}/futures-positions", response_model=AccountSnapshotView)
def get_futures_positions(
    account_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
) -> AccountSnapshotView:
    require_connector_runtime(runtime)
    try:
        return service.snapshot(
            tenant_id=principal.tenant_id,
            account_id=account_id,
            scope=AccountScopeType.USDM_FUTURES,
        )
    except (LookupError, TradingGuardError, BinanceConnectorError, ValueError) as error:
        raise _operation_error(error) from error


@router.post(
    "/{account_id}/margin-loans",
    response_model=TradingOperationView,
    status_code=status.HTTP_201_CREATED,
)
def borrow_margin(
    account_id: str,
    payload: MarginTransactionPayload,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=80),
    ],
    risk_approval: Annotated[
        str,
        Header(alias="X-Risk-Approval", min_length=8, max_length=512),
    ],
) -> TradingOperationView:
    require_live_runtime(runtime)
    return _margin_transaction(
        service=service,
        principal=principal,
        account_id=account_id,
        payload=payload,
        idempotency_key=idempotency_key,
        risk_approval=risk_approval,
        action="BORROW",
    )


@router.post(
    "/{account_id}/margin-repayments",
    response_model=TradingOperationView,
    status_code=status.HTTP_201_CREATED,
)
def repay_margin(
    account_id: str,
    payload: MarginTransactionPayload,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=80),
    ],
) -> TradingOperationView:
    require_connector_runtime(runtime)
    return _margin_transaction(
        service=service,
        principal=principal,
        account_id=account_id,
        payload=payload,
        idempotency_key=idempotency_key,
        risk_approval="",
        action="REPAY",
    )


@router.put(
    "/{account_id}/futures-settings",
    response_model=TradingOperationView,
)
def set_futures_leverage(
    account_id: str,
    payload: FuturesLeveragePayload,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[
        AccountOperationsService,
        Depends(get_account_operations_service),
    ],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=80),
    ],
    risk_approval: Annotated[
        str,
        Header(alias="X-Risk-Approval", min_length=8, max_length=512),
    ],
) -> TradingOperationView:
    require_live_runtime(runtime)
    try:
        return service.set_futures_leverage(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
            idempotency_key=idempotency_key,
            risk_approval_token=risk_approval,
            command=FuturesLeverageCommand(
                account_id=account_id,
                symbol=payload.symbol,
                leverage=payload.leverage,
            ),
        )
    except (
        PermissionError,
        LookupError,
        BinanceConnectorError,
        IdempotencyConflictError,
        TradingGuardError,
        ValueError,
    ) as error:
        raise _operation_error(error) from error


def _margin_transaction(
    *,
    service: AccountOperationsService,
    principal: Principal,
    account_id: str,
    payload: MarginTransactionPayload,
    idempotency_key: str,
    risk_approval: str,
    action: str,
) -> TradingOperationView:
    try:
        return service.margin_transaction(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
            idempotency_key=idempotency_key,
            risk_approval_token=risk_approval,
            action=action,
            command=MarginTransactionCommand(
                account_id=account_id,
                account_scope=payload.account_scope,
                symbol=payload.symbol,
                asset=payload.asset,
                amount=payload.amount,
            ),
        )
    except (
        PermissionError,
        LookupError,
        BinanceConnectorError,
        IdempotencyConflictError,
        TradingGuardError,
        ValueError,
    ) as error:
        raise _operation_error(error) from error


def _operation_error(error: Exception) -> ServiceError:
    if isinstance(error, BinanceConnectorError):
        return ServiceError(
            code=error.code,
            message=str(error),
            status_code=502,
        )
    if isinstance(error, PermissionError):
        return ServiceError(
            code="authorization.denied",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, LookupError):
        return ServiceError(
            code="resource.not_found",
            message=str(error),
            status_code=404,
        )
    if isinstance(error, IdempotencyConflictError):
        return ServiceError(
            code="idempotency.conflict",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, TradingGuardError):
        return ServiceError(
            code="trading.guard_rejected",
            message=str(error),
            status_code=409,
        )
    return ServiceError(
        code="trading.operation_invalid",
        message=str(error),
        status_code=422,
    )
