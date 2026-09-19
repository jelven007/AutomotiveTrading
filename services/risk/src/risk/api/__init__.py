from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from risk.authorizations import (
    AuthorizationError,
    AuthorizationIssueResult,
    PolicyNotFoundError,
    RiskAuthorizationService,
)
from risk.config import get_settings
from risk.db import get_session
from risk.errors import ServiceError
from risk.policy import OrderRiskInput, RiskPolicy, RiskSnapshot
from risk.security import ServiceIdentity, require_service_identity

router = APIRouter(
    prefix="/api/v1/risk",
    tags=["risk"],
    dependencies=[Depends(require_service_identity)],
)


class PolicyView(BaseModel):
    tenant_id: str
    version: int
    policy: RiskPolicy


class AuthorizationIssueRequest(BaseModel):
    tenant_id: str
    account_id: str
    order: OrderRiskInput
    snapshot: RiskSnapshot


class AuthorizationVerifyRequest(BaseModel):
    tenant_id: str
    account_id: str
    order: OrderRiskInput


def get_authorization_service(
    session: Annotated[Session, Depends(get_session)],
) -> RiskAuthorizationService:
    return RiskAuthorizationService(
        session,
        token_ttl_seconds=get_settings().approval_ttl_seconds,
    )


@router.put("/policies/{tenant_id}", response_model=PolicyView)
def set_policy(
    tenant_id: str,
    policy: RiskPolicy,
    service: Annotated[RiskAuthorizationService, Depends(get_authorization_service)],
    _identity: Annotated[ServiceIdentity, Depends(require_service_identity)],
) -> PolicyView:
    version = service.set_policy(tenant_id, policy)
    return PolicyView(tenant_id=tenant_id, version=version, policy=policy)


@router.get("/policies/{tenant_id}", response_model=PolicyView)
def get_policy(
    tenant_id: str,
    service: Annotated[RiskAuthorizationService, Depends(get_authorization_service)],
    _identity: Annotated[ServiceIdentity, Depends(require_service_identity)],
) -> PolicyView:
    try:
        version, policy = service.get_policy(tenant_id)
    except PolicyNotFoundError as error:
        raise ServiceError(
            code="risk.policy_not_found",
            message="Active risk policy not found",
            status_code=404,
        ) from error
    return PolicyView(tenant_id=tenant_id, version=version, policy=policy)


@router.post(
    "/order-authorizations",
    response_model=AuthorizationIssueResult,
    status_code=status.HTTP_201_CREATED,
)
def issue_authorization(
    payload: AuthorizationIssueRequest,
    service: Annotated[RiskAuthorizationService, Depends(get_authorization_service)],
    _identity: Annotated[ServiceIdentity, Depends(require_service_identity)],
) -> AuthorizationIssueResult:
    try:
        return service.issue(
            tenant_id=payload.tenant_id,
            account_id=payload.account_id,
            order_payload=payload.order.model_dump(mode="json"),
            snapshot_payload=payload.snapshot.model_dump(mode="json"),
        )
    except PolicyNotFoundError as error:
        raise ServiceError(
            code="risk.policy_not_found",
            message="Active risk policy not found",
            status_code=409,
        ) from error


@router.post("/order-authorizations/verify")
def verify_authorization(
    payload: AuthorizationVerifyRequest,
    approval_token: Annotated[
        str,
        Header(alias="X-Risk-Approval", min_length=32, max_length=256),
    ],
    service: Annotated[RiskAuthorizationService, Depends(get_authorization_service)],
    _identity: Annotated[ServiceIdentity, Depends(require_service_identity)],
) -> dict[str, bool]:
    try:
        approved = service.verify_and_consume(
            tenant_id=payload.tenant_id,
            account_id=payload.account_id,
            order_payload=payload.order.model_dump(mode="json"),
            approval_token=approval_token,
        )
    except AuthorizationError:
        approved = False
    return {"approved": approved}
