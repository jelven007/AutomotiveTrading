from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field

from trading.api.dependencies import (
    RuntimeGuard,
    get_order_service,
    get_runtime_guard,
    require_connector_runtime,
    require_live_runtime,
)
from trading.errors import ServiceError
from trading.orders import (
    IdempotencyConflictError,
    OrderCommand,
    OrderService,
    OrderView,
    TradingGuardError,
)
from trading.security import Principal, get_principal

router = APIRouter(prefix="/api/v1/trading", tags=["trading-orders"])


class KillSwitchCommand(BaseModel):
    reason: str = Field(min_length=3, max_length=255)
    scope: str = Field(default="global", min_length=1, max_length=80)


@router.get("/orders", response_model=list[OrderView])
def list_orders(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> list[OrderView]:
    return service.list_for_tenant(principal.tenant_id)


@router.post(
    "/orders",
    response_model=OrderView,
    status_code=status.HTTP_201_CREATED,
)
def submit_order(
    payload: OrderCommand,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=80),
    ],
    risk_approval: Annotated[
        str,
        Header(alias="X-Risk-Approval", min_length=8, max_length=512),
    ],
) -> OrderView:
    require_live_runtime(runtime)
    try:
        return service.submit(
            tenant_id=principal.tenant_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
            idempotency_key=idempotency_key,
            risk_approval_token=risk_approval,
            command=payload,
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
    except IdempotencyConflictError as error:
        raise ServiceError(
            code="idempotency.conflict",
            message=str(error),
            status_code=409,
        ) from error
    except TradingGuardError as error:
        raise ServiceError(
            code="trading.guard_rejected",
            message=str(error),
            status_code=409,
        ) from error
    except ValueError as error:
        raise ServiceError(
            code="trading.order_invalid",
            message=str(error),
            status_code=422,
        ) from error


@router.get("/orders/{order_id}", response_model=OrderView)
def get_order(
    order_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderView:
    try:
        return service.get(principal.tenant_id, order_id)
    except LookupError as error:
        raise ServiceError(
            code="resource.not_found",
            message=str(error),
            status_code=404,
        ) from error


@router.post("/orders/{order_id}/cancel", response_model=OrderView)
def cancel_order(
    order_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
    runtime: Annotated[RuntimeGuard, Depends(get_runtime_guard)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=80),
    ],
) -> OrderView:
    require_connector_runtime(runtime)
    try:
        return service.cancel(
            tenant_id=principal.tenant_id,
            order_id=order_id,
            actor_roles=principal.roles,
            mfa_verified_at=principal.mfa_verified_at,
            idempotency_key=idempotency_key,
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
    except IdempotencyConflictError as error:
        raise ServiceError(
            code="idempotency.conflict",
            message=str(error),
            status_code=409,
        ) from error
    except TradingGuardError as error:
        raise ServiceError(
            code="trading.guard_rejected",
            message=str(error),
            status_code=409,
        ) from error


@router.post(
    "/kill-switch",
    status_code=status.HTTP_201_CREATED,
)
def activate_kill_switch(
    payload: KillSwitchCommand,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> dict[str, str | bool]:
    if not {"tenant_admin", "trader"}.intersection(principal.roles):
        raise ServiceError(
            code="authorization.denied",
            message="Trader role is required",
            status_code=403,
        )
    switch = service.activate_kill_switch(
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
        scope=payload.scope,
    )
    return {
        "id": switch.id,
        "scope": switch.scope,
        "active": switch.active,
    }


@router.delete("/kill-switch/{switch_id}")
def release_kill_switch(
    switch_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> dict[str, str | bool]:
    try:
        switch = service.release_kill_switch(
            tenant_id=principal.tenant_id,
            switch_id=switch_id,
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
    return {
        "id": switch.id,
        "scope": switch.scope,
        "active": switch.active,
    }
