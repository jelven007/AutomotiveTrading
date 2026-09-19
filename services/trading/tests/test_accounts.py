import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from trading.accounts import (
    AccountBindCommand,
    AccountPermissionSnapshot,
    TradingAccountService,
)
from trading.models import OutboxEvent, TradingAccount
from trading.secrets import InMemoryEncryptedSecretBackend


class StubPermissionProbe:
    def __init__(self, snapshot: AccountPermissionSnapshot) -> None:
        self.snapshot = snapshot

    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        return self.snapshot


def permission_snapshot(**overrides: object) -> AccountPermissionSnapshot:
    values: dict[str, object] = {
        "external_account_ref": "binance-user-42",
        "can_read": True,
        "can_spot_trade": True,
        "can_margin_trade": True,
        "can_futures_trade": True,
        "can_withdraw": False,
    }
    values.update(overrides)
    return AccountPermissionSnapshot.model_validate(values)


def binance_command(**overrides: object) -> AccountBindCommand:
    values: dict[str, object] = {
        "alias": "主帐号",
        "market_group": "binance",
        "provider": "binance",
        "environment": "production",
        "credential_type": "ed25519",
        "api_key": "api-key-sensitive",
        "private_key_or_secret": "private-key-sensitive",
        "enabled_scopes": [
            "spot",
            "cross_margin",
            "isolated_margin",
            "usdm_futures",
        ],
        "isolated_symbols": ["BTCUSDT"],
        "ip_whitelist_confirmed": True,
    }
    values.update(overrides)
    return AccountBindCommand.model_validate(values)


def service(
    session: Session,
    *,
    snapshot: AccountPermissionSnapshot | None = None,
) -> tuple[TradingAccountService, InMemoryEncryptedSecretBackend]:
    backend = InMemoryEncryptedSecretBackend()
    account_service = TradingAccountService(
        session,
        backend,
        StubPermissionProbe(snapshot or permission_snapshot()),
    )
    return account_service, backend


def test_binance_binding_externalizes_credentials_and_starts_read_only(
    session: Session,
) -> None:
    account_service, backend = service(session)

    result = account_service.bind(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
        command=binance_command(),
    )

    stored = session.scalar(select(TradingAccount))
    assert stored is not None
    assert stored.secret_ref is not None
    assert backend.get(stored.secret_ref) == {
        "api_key": "api-key-sensitive",
        "private_key_or_secret": "private-key-sensitive",
    }
    serialized = json.dumps(result.model_dump(mode="json"))
    assert "api-key-sensitive" not in serialized
    assert "private-key-sensitive" not in serialized
    assert result.api_key_fingerprint.startswith("sha256:")
    assert result.status == "read_only"
    assert result.trading_enabled is False
    assert {(scope.scope_type, scope.symbol) for scope in result.scopes} == {
        ("spot", None),
        ("cross_margin", None),
        ("isolated_margin", "BTCUSDT"),
        ("usdm_futures", None),
    }
    outbox = session.scalar(select(OutboxEvent))
    assert outbox is not None
    assert "api-key-sensitive" not in outbox.payload_json
    assert "private-key-sensitive" not in outbox.payload_json


def test_account_listing_is_tenant_isolated(session: Session) -> None:
    account_service, _ = service(session)
    account_service.bind(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
        command=binance_command(),
    )

    assert len(account_service.list_for_tenant("tenant-a")) == 1
    assert account_service.list_for_tenant("tenant-b") == []


def test_binding_requires_tenant_admin_and_recent_mfa(session: Session) -> None:
    account_service, _ = service(session)

    with pytest.raises(PermissionError, match="tenant administrator"):
        account_service.bind(
            tenant_id="tenant-a",
            actor_roles=("trader",),
            mfa_verified_at=datetime.now(UTC),
            command=binance_command(),
        )
    with pytest.raises(PermissionError, match="recent MFA"):
        account_service.bind(
            tenant_id="tenant-a",
            actor_roles=("tenant_admin",),
            mfa_verified_at=datetime.now(UTC) - timedelta(minutes=6),
            command=binance_command(),
        )


def test_binance_binding_rejects_withdrawal_permission_without_storing_secret(
    session: Session,
) -> None:
    account_service, backend = service(
        session,
        snapshot=permission_snapshot(can_withdraw=True),
    )

    with pytest.raises(ValueError, match="withdrawal permission"):
        account_service.bind(
            tenant_id="tenant-a",
            actor_roles=("tenant_admin",),
            mfa_verified_at=datetime.now(UTC),
            command=binance_command(),
        )

    assert session.scalar(select(TradingAccount)) is None
    assert backend.count == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("environment", "testnet", "production"),
        ("ip_whitelist_confirmed", False, "IP whitelist"),
        ("isolated_symbols", [], "isolated symbols"),
    ],
)
def test_binance_binding_validates_production_guards(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        binance_command(**{field: value})


def test_market_provider_whitelist_is_enforced() -> None:
    with pytest.raises(ValueError, match="provider"):
        AccountBindCommand(
            alias="错误通道",
            market_group="cn_equity",
            provider="binance",
            environment="production",
        )


def test_permission_recheck_disables_account_when_withdrawal_is_enabled(
    session: Session,
) -> None:
    probe = StubPermissionProbe(permission_snapshot())
    backend = InMemoryEncryptedSecretBackend()
    account_service = TradingAccountService(session, backend, probe)
    account = account_service.bind(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
        command=binance_command(),
    )
    account_service.enable_trading(
        tenant_id="tenant-a",
        account_id=account.id,
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
    )
    probe.snapshot = permission_snapshot(can_withdraw=True)

    with pytest.raises(ValueError, match="withdrawal permission"):
        account_service.test_connection(
            tenant_id="tenant-a",
            account_id=account.id,
            actor_roles=("tenant_admin",),
        )

    disabled = account_service.list_for_tenant("tenant-a")[0]
    assert disabled.status == "disabled"
    assert disabled.trading_enabled is False
