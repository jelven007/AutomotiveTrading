from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from trading.account_operations import AccountOperationsService
from trading.accounts import TradingAccountService
from trading.binance.client import BinanceClient
from trading.config import SecretBackendType, get_settings
from trading.db import get_session
from trading.errors import ServiceError
from trading.orders import OrderService
from trading.risk import DenyAllRiskAuthorizer, HttpRiskAuthorizer, RiskAuthorizer
from trading.secrets import (
    HttpKmsSecretBackend,
    LocalEncryptedSecretBackend,
    SecretBackend,
)


@dataclass(frozen=True)
class RuntimeGuard:
    external_kms_configured: bool
    fixed_egress_ip_configured: bool
    live_trading_enabled: bool
    risk_service_configured: bool


def get_runtime_guard() -> RuntimeGuard:
    settings = get_settings()
    return RuntimeGuard(
        external_kms_configured=settings.secret_backend is SecretBackendType.KMS
        and bool(settings.kms_url),
        fixed_egress_ip_configured=settings.fixed_egress_ip_configured,
        live_trading_enabled=settings.live_trading_enabled,
        risk_service_configured=bool(settings.risk_service_url),
    )


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client(follow_redirects=False) as client:
        yield client


def get_secret_backend(
    session: Annotated[Session, Depends(get_session)],
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> SecretBackend:
    settings = get_settings()
    if settings.secret_backend is SecretBackendType.KMS:
        if not settings.kms_url:
            raise ServiceError(
                code="trading.kms_unavailable",
                message="External KMS is not configured",
                status_code=503,
            )
        token = settings.kms_access_token.get_secret_value() if settings.kms_access_token else None
        return HttpKmsSecretBackend(http, settings.kms_url, token)
    if settings.local_secret_encryption_key is None:
        raise ServiceError(
            code="trading.local_secret_key_missing",
            message="Local secret encryption key is not configured",
            status_code=503,
        )
    return LocalEncryptedSecretBackend(
        session,
        settings.local_secret_encryption_key.get_secret_value(),
    )


def get_binance_client(
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> BinanceClient:
    settings = get_settings()
    return BinanceClient(
        http=http,
        spot_base_url=settings.binance_spot_base_url,
        futures_base_url=settings.binance_futures_base_url,
    )


def get_risk_authorizer(
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> RiskAuthorizer:
    settings = get_settings()
    if not settings.live_trading_enabled or not settings.risk_service_url:
        return DenyAllRiskAuthorizer()
    return HttpRiskAuthorizer(http, settings.risk_service_url)


def get_account_service(
    session: Annotated[Session, Depends(get_session)],
    secret_backend: Annotated[SecretBackend, Depends(get_secret_backend)],
    binance_client: Annotated[BinanceClient, Depends(get_binance_client)],
) -> TradingAccountService:
    return TradingAccountService(session, secret_backend, binance_client)


def get_order_service(
    session: Annotated[Session, Depends(get_session)],
    secret_backend: Annotated[SecretBackend, Depends(get_secret_backend)],
    binance_client: Annotated[BinanceClient, Depends(get_binance_client)],
    risk_authorizer: Annotated[RiskAuthorizer, Depends(get_risk_authorizer)],
) -> OrderService:
    return OrderService(
        session,
        secret_backend,
        binance_client,
        risk_authorizer,
    )


def get_account_operations_service(
    session: Annotated[Session, Depends(get_session)],
    secret_backend: Annotated[SecretBackend, Depends(get_secret_backend)],
    binance_client: Annotated[BinanceClient, Depends(get_binance_client)],
    risk_authorizer: Annotated[RiskAuthorizer, Depends(get_risk_authorizer)],
) -> AccountOperationsService:
    return AccountOperationsService(
        session,
        secret_backend,
        binance_client,
        risk_authorizer,
        max_futures_leverage=get_settings().max_futures_leverage,
    )


def require_binding_runtime(guard: RuntimeGuard) -> None:
    if not guard.fixed_egress_ip_configured:
        raise ServiceError(
            code="trading.fixed_egress_required",
            message="A fixed egress IP must be configured before binding Binance",
            status_code=409,
        )


def require_live_runtime(guard: RuntimeGuard) -> None:
    require_connector_runtime(guard)
    if not guard.risk_service_configured:
        raise ServiceError(
            code="trading.risk_service_required",
            message="Risk service is required for live trading",
            status_code=409,
        )
    if not guard.live_trading_enabled:
        raise ServiceError(
            code="trading.live_disabled",
            message="Live trading is disabled",
            status_code=409,
        )


def require_connector_runtime(guard: RuntimeGuard) -> None:
    if not guard.external_kms_configured:
        raise ServiceError(
            code="trading.kms_required",
            message="External KMS is required for live trading",
            status_code=409,
        )
    if not guard.fixed_egress_ip_configured:
        raise ServiceError(
            code="trading.fixed_egress_required",
            message="A fixed egress IP is required for live trading",
            status_code=409,
        )
