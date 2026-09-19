from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session
from trading.account_operations import (
    AccountOperationsService,
    FuturesLeverageCommand,
    MarginTransactionCommand,
)
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
from trading.orders import TradingGuardError
from trading.secrets import InMemoryEncryptedSecretBackend


class StubRiskAuthorizer:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved

    def authorize(self, **_: object) -> bool:
        return self.approved


class StubAccountConnector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def account_snapshot(self, **values: object) -> dict[str, object]:
        self.calls.append(("snapshot", values))
        return {"balances": [{"asset": "USDT", "free": "100.00"}]}

    def margin_borrow_repay(self, **values: object) -> str:
        self.calls.append(("margin", values))
        return "transaction-1"

    def set_futures_leverage(self, **values: object) -> dict[str, object]:
        self.calls.append(("leverage", values))
        return {"symbol": values["symbol"], "leverage": values["leverage"]}


def account_and_secrets(
    session: Session,
) -> tuple[TradingAccount, InMemoryEncryptedSecretBackend]:
    secret_backend = InMemoryEncryptedSecretBackend()
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
    return account, secret_backend


def test_reads_real_account_snapshot_without_write_approval(session: Session) -> None:
    account, secret_backend = account_and_secrets(session)
    connector = StubAccountConnector()
    operations = AccountOperationsService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(approved=False),
    )

    result = operations.snapshot(
        tenant_id="tenant-a",
        account_id=account.id,
        scope=AccountScopeType.USDM_FUTURES,
    )

    assert result.data["balances"][0]["free"] == "100.00"
    assert connector.calls[0][0] == "snapshot"


@pytest.mark.parametrize("action", ["BORROW", "REPAY"])
def test_margin_transactions_are_idempotent(
    session: Session,
    action: str,
) -> None:
    account, secret_backend = account_and_secrets(session)
    connector = StubAccountConnector()
    operations = AccountOperationsService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )
    command = MarginTransactionCommand(
        account_id=account.id,
        account_scope="isolated_margin",
        symbol="BTCUSDT",
        asset="USDT",
        amount="10",
    )

    first = operations.margin_transaction(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key=f"{action.lower()}-key",
        risk_approval_token="risk-approved",
        action=action,
        command=command,
    )
    repeated = operations.margin_transaction(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key=f"{action.lower()}-key",
        risk_approval_token="risk-approved",
        action=action,
        command=command,
    )

    assert first.status == "completed"
    assert repeated.id == first.id
    assert len(connector.calls) == 1


def test_expired_trading_authority_blocks_borrow_but_allows_repayment(
    session: Session,
) -> None:
    account, secret_backend = account_and_secrets(session)
    account.trading_authority_expiration_time_ms = 1
    session.commit()
    connector = StubAccountConnector()
    operations = AccountOperationsService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
    )
    command = MarginTransactionCommand(
        account_id=account.id,
        account_scope="cross_margin",
        asset="USDT",
        amount="10",
    )

    with pytest.raises(TradingGuardError, match="not enabled"):
        operations.margin_transaction(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            idempotency_key="expired-borrow",
            risk_approval_token="risk-approved",
            action="BORROW",
            command=command,
        )

    repaid = operations.margin_transaction(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="expired-repay",
        risk_approval_token="",
        action="REPAY",
        command=command,
    )
    assert repaid.status == "completed"


def test_futures_leverage_respects_platform_cap_and_risk_approval(
    session: Session,
) -> None:
    account, secret_backend = account_and_secrets(session)
    connector = StubAccountConnector()
    operations = AccountOperationsService(
        session,
        secret_backend,
        connector,
        StubRiskAuthorizer(),
        max_futures_leverage=20,
    )

    with pytest.raises(ValueError, match="platform leverage limit"):
        operations.set_futures_leverage(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            idempotency_key="leverage-50",
            risk_approval_token="risk-approved",
            command=FuturesLeverageCommand(
                account_id=account.id,
                symbol="BTCUSDT",
                leverage=50,
            ),
        )

    result = operations.set_futures_leverage(
        tenant_id="tenant-a",
        actor_roles=("trader",),
        mfa_verified_at=datetime.now(UTC),
        idempotency_key="leverage-5",
        risk_approval_token="risk-approved",
        command=FuturesLeverageCommand(
            account_id=account.id,
            symbol="BTCUSDT",
            leverage=5,
        ),
    )
    assert result.status == "completed"
    assert result.broker_reference == "BTCUSDT:5"
