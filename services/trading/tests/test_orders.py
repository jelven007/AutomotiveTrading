from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from trading.binance.client import BinanceCredentials
from trading.binance.errors import BinanceWriteTimeout
from trading.models import (
    AccountScopeType,
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingAccountScope,
    TradingProvider,
)
from trading.orders import (
    IdempotencyConflictError,
    OrderCommand,
    OrderExecutionResult,
    OrderService,
    TradingGuardError,
)
from trading.secrets import InMemoryEncryptedSecretBackend


class StubRiskAuthorizer:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved

    def authorize(self, **_: object) -> bool:
        return self.approved


class StubExecutionConnector:
    def __init__(self, *, timeout: bool = False) -> None:
        self.timeout = timeout
        self.calls: list[dict[str, object]] = []
        self.cancel_calls: list[dict[str, object]] = []

    def submit_order(self, **values: object) -> OrderExecutionResult:
        self.calls.append(values)
        if self.timeout:
            raise BinanceWriteTimeout()
        return OrderExecutionResult(
            broker_order_id="987654",
            status="submitted",
            filled_quantity="0",
        )

    def cancel_order(self, **values: object) -> OrderExecutionResult:
        self.cancel_calls.append(values)
        if self.timeout:
            raise BinanceWriteTimeout()
        return OrderExecutionResult(
            broker_order_id="987654",
            status="cancelled",
            filled_quantity="0",
        )


def enabled_account(
    session: Session,
    secret_backend: InMemoryEncryptedSecretBackend,
) -> TradingAccount:
    secret_ref = secret_backend.put(
        "tenant-a",
        {
            "api_key": "production-api-key",
            "private_key_or_secret": "hmac-secret",
        },
    )
    account = TradingAccount(
        tenant_id="tenant-a",
        alias="主帐号",
        market_group=MarketGroup.BINANCE,
        provider=TradingProvider.BINANCE,
        environment="production",
        credential_type=CredentialType.HMAC,
        api_key_fingerprint="sha256:test",
        secret_ref=secret_ref,
        status=AccountStatus.ACTIVE,
        connection_status=ConnectionStatus.CONNECTED,
        trading_enabled=True,
        ip_restricted=True,
        can_read=True,
        can_spot_trade=True,
        can_margin_trade=True,
        can_futures_trade=True,
        can_withdraw=False,
        can_internal_transfer=False,
        can_universal_transfer=False,
        created_by="user-a",
    )
    session.add(account)
    session.flush()
    for scope in AccountScopeType:
        session.add(
            TradingAccountScope(
                tenant_id="tenant-a",
                account_id=account.id,
                scope_type=scope,
                scope_key="BTCUSDT" if scope is AccountScopeType.ISOLATED_MARGIN else "global",
                symbol="BTCUSDT" if scope is AccountScopeType.ISOLATED_MARGIN else None,
                enabled=True,
                status="verified",
            )
        )
    session.commit()
    return account


def command(account_id: str, scope: AccountScopeType, **overrides: object) -> OrderCommand:
    values: dict[str, object] = {
        "account_id": account_id,
        "account_scope": scope,
        "symbol": "BTCUSDT",
        "side": "buy",
        "order_type": "limit",
        "quantity": "0.01",
        "limit_price": "50000",
        "time_in_force": "GTC",
        "position_side": "both" if scope is AccountScopeType.USDM_FUTURES else None,
        "reduce_only": False,
        "margin_side_effect": "none",
        "source": "manual",
    }
    values.update(overrides)
    return OrderCommand.model_validate(values)


@pytest.mark.parametrize("scope", list(AccountScopeType))
def test_submit_routes_each_binance_scope_with_protected_credentials(
    session: Session,
    scope: AccountScopeType,
) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    connector = StubExecutionConnector()
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )

    result = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key=f"order-{scope.value}",
        risk_approval_token="risk-approved",
        command=command(account.id, scope),
    )

    assert result.status == "submitted"
    assert result.broker_order_id == "987654"
    assert connector.calls[0]["scope"] is scope
    assert connector.calls[0]["credentials"] == BinanceCredentials(
        api_key="production-api-key",
        private_key_or_secret="hmac-secret",
        credential_type=CredentialType.HMAC,
    )


def test_idempotency_returns_same_order_and_rejects_payload_change(session: Session) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    connector = StubExecutionConnector()
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )
    first = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="stable-key",
        risk_approval_token="risk-approved",
        command=command(account.id, AccountScopeType.SPOT),
    )
    repeated = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="stable-key",
        risk_approval_token="risk-approved",
        command=command(account.id, AccountScopeType.SPOT),
    )

    assert repeated.id == first.id
    assert len(connector.calls) == 1
    with pytest.raises(IdempotencyConflictError):
        order_service.submit(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            idempotency_key="stable-key",
            risk_approval_token="risk-approved",
            command=command(
                account.id,
                AccountScopeType.SPOT,
                quantity="0.02",
            ),
        )


def test_write_timeout_is_persisted_as_unknown_and_not_retried(session: Session) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    connector = StubExecutionConnector(timeout=True)
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )

    first = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="timeout-key",
        risk_approval_token="risk-approved",
        command=command(account.id, AccountScopeType.USDM_FUTURES),
    )
    repeated = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="timeout-key",
        risk_approval_token="risk-approved",
        command=command(account.id, AccountScopeType.USDM_FUTURES),
    )

    assert first.status == "unknown"
    assert repeated.id == first.id
    assert len(connector.calls) == 1


@pytest.mark.parametrize(
    ("roles", "mfa_age", "risk_approved", "expected"),
    [
        (("researcher",), 0, True, "trader role"),
        (("trader",), 301, True, "recent MFA"),
        (("trader",), 0, False, "risk approval"),
    ],
)
def test_order_guards_fail_closed(
    session: Session,
    roles: tuple[str, ...],
    mfa_age: int,
    risk_approved: bool,
    expected: str,
) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    order_service = OrderService(
        session,
        secret_backend,
        StubExecutionConnector(),
        StubRiskAuthorizer(risk_approved),
    )

    with pytest.raises((PermissionError, TradingGuardError), match=expected):
        order_service.submit(
            tenant_id="tenant-a",
            actor_roles=roles,
            mfa_verified_at=datetime.now(UTC) - timedelta(seconds=mfa_age),
            idempotency_key=f"guard-{expected}",
            risk_approval_token="risk-approved",
            command=command(account.id, AccountScopeType.SPOT),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ip_restricted", False),
        ("can_withdraw", True),
        ("can_internal_transfer", True),
        ("can_universal_transfer", True),
        ("trading_authority_expiration_time_ms", 1),
    ],
)
def test_order_guard_rejects_unsafe_api_key_permissions(
    session: Session,
    field: str,
    value: bool | int,
) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    setattr(account, field, value)
    session.commit()
    order_service = OrderService(
        session,
        secret_backend,
        StubExecutionConnector(),
        StubRiskAuthorizer(),
    )

    with pytest.raises(TradingGuardError, match="not enabled"):
        order_service.submit(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            idempotency_key=f"unsafe-{field}",
            risk_approval_token="risk-approved",
            command=command(account.id, AccountScopeType.SPOT),
        )


def test_active_kill_switch_blocks_order_submission(session: Session) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    connector = StubExecutionConnector()
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )
    order_service.activate_kill_switch(
        tenant_id="tenant-a",
        actor_user_id="operator-a",
        reason="manual incident response",
    )

    with pytest.raises(TradingGuardError, match="kill switch"):
        order_service.submit(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            idempotency_key="blocked-order",
            risk_approval_token="risk-approved",
            command=command(account.id, AccountScopeType.SPOT),
        )
    assert connector.calls == []


def test_cancel_uses_independent_idempotency_and_is_not_blocked_by_kill_switch(
    session: Session,
) -> None:
    secret_backend = InMemoryEncryptedSecretBackend()
    account = enabled_account(session, secret_backend)
    connector = StubExecutionConnector()
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )
    submitted = order_service.submit(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="submit-key",
        risk_approval_token="risk-approved",
        command=command(account.id, AccountScopeType.SPOT),
    )
    order_service.activate_kill_switch(
        tenant_id="tenant-a",
        actor_user_id="operator-a",
        reason="stop new exposure",
    )

    cancelled = order_service.cancel(
        tenant_id="tenant-a",
        order_id=submitted.id,
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="cancel-key",
    )
    repeated = order_service.cancel(
        tenant_id="tenant-a",
        order_id=submitted.id,
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="cancel-key",
    )

    assert cancelled.status == "cancelled"
    assert repeated.id == cancelled.id
    assert len(connector.cancel_calls) == 1
