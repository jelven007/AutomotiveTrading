from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from trading.binance.client import BinanceDemoAccountProbe
from trading.binance_runtime.manager import SingleNautilusRuntimeManager
from trading.binance_runtime.nautilus import NautilusRuntimeFactory
from trading.binance_runtime.overview import BinanceOverviewCache
from trading.config import get_settings
from trading.db import get_session
from trading.errors import ServiceError
from trading.secrets import LocalAesGcmSecretBackend, LocalCredentialVault, SecretBackend


@dataclass(frozen=True)
class RuntimeGuard:
    fixed_egress_ip_configured: bool


def get_runtime_guard() -> RuntimeGuard:
    settings = get_settings()
    return RuntimeGuard(
        fixed_egress_ip_configured=settings.fixed_egress_ip_configured,
    )


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client(follow_redirects=False) as client:
        yield client


def get_secret_backend(
    session: Annotated[Session, Depends(get_session)],
) -> SecretBackend:
    settings = get_settings()
    try:
        vault = LocalCredentialVault.from_file(settings.binance_credential_master_key_file)
    except (FileNotFoundError, PermissionError, OSError, ValueError) as error:
        raise ServiceError(
            code="trading.local_secret_key_missing",
            message="Local credential master key is unavailable",
            status_code=503,
        ) from error
    return LocalAesGcmSecretBackend(session, vault)


def get_binance_client(
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> BinanceDemoAccountProbe:
    return BinanceDemoAccountProbe(http=http)


@lru_cache
def get_binance_runtime_manager() -> SingleNautilusRuntimeManager:
    return SingleNautilusRuntimeManager(NautilusRuntimeFactory())


@lru_cache
def get_binance_overview_cache() -> BinanceOverviewCache:
    return BinanceOverviewCache()


def require_binding_runtime(guard: RuntimeGuard) -> None:
    if not guard.fixed_egress_ip_configured:
        raise ServiceError(
            code="trading.fixed_egress_required",
            message="A fixed egress IP must be configured before binding Binance",
            status_code=409,
        )


__all__ = [
    "RuntimeGuard",
    "get_binance_client",
    "get_binance_overview_cache",
    "get_binance_runtime_manager",
    "get_runtime_guard",
    "get_secret_backend",
    "require_binding_runtime",
]
