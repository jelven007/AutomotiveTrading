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
from trading.binance.errors import BinanceConnectorError
from trading.models import OutboxEvent, TradingAccount
from trading.secrets import InMemoryEncryptedSecretBackend


class StubPermissionProbe:
    def __init__(self, snapshot: AccountPermissionSnapshot) -> None:
        self.snapshot = snapshot

    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        return self.snapshot


class FailingPermissionProbe:
    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        raise BinanceConnectorError(
            "binance.credentials_invalid",
            "Binance API credentials or permissions are invalid",
        )


def permission_snapshot(**overrides: object) -> AccountPermissionSnapshot:
    values: dict[str, object] = {
        "external_account_ref": "binance-user-42",
        "ip_restricted": True,
        "can_read": True,
        "can_spot_trade": True,
        "can_margin_trade": True,
        "can_futures_trade": True,
        "can_withdraw": False,
        "can_internal_transfer": False,
        "can_universal_transfer": False,
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
    assert stored.ip_restricted is True
    assert stored.can_universal_transfer is False
    assert backend.get("tenant-a", stored.secret_ref) == {
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


def test_read_only_binance_key_can_bind_but_cannot_enable_trading(
    session: Session,
) -> None:
    account_service, _ = service(
        session,
        snapshot=permission_snapshot(
            can_spot_trade=False,
            can_margin_trade=False,
            can_futures_trade=False,
        ),
    )

    bound = account_service.bind(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
        command=binance_command(),
    )
    checked = account_service.test_connection(
        tenant_id="tenant-a",
        account_id=bound.id,
        actor_roles=("tenant_admin",),
    )

    assert checked.status == "read_only"
    assert checked.connection_status == "connected"
    assert checked.trading_enabled is False
    assert all(scope.enabled is False for scope in checked.scopes)
    with pytest.raises(ValueError, match="missing trading permissions"):
        account_service.enable_trading(
            tenant_id="tenant-a",
            account_id=bound.id,
            actor_roles=("tenant_admin",),
            mfa_verified_at=datetime.now(UTC),
        )


def test_expired_spot_margin_authority_cannot_enable_trading(
    session: Session,
) -> None:
    account_service, _ = service(
        session,
        snapshot=permission_snapshot(
            trading_authority_expiration_time_ms=1,
        ),
    )
    bound = account_service.bind(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
        command=binance_command(enabled_scopes=["spot", "cross_margin"]),
    )

    with pytest.raises(ValueError, match="missing trading permissions"):
        account_service.enable_trading(
            tenant_id="tenant-a",
            account_id=bound.id,
            actor_roles=("tenant_admin",),
            mfa_verified_at=datetime.now(UTC),
        )


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
    ("overrides", "message"),
    [
        ({"ip_restricted": False}, "IP restriction"),
        ({"can_internal_transfer": True}, "internal transfer"),
        ({"can_universal_transfer": True}, "universal transfer"),
    ],
)
def test_binance_binding_rejects_unsafe_key_restrictions(
    session: Session,
    overrides: dict[str, bool],
    message: str,
) -> None:
    account_service, backend = service(
        session,
        snapshot=permission_snapshot(**overrides),
    )

    with pytest.raises(ValueError, match=message):
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


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"can_withdraw": True}, "withdrawal permission"),
        ({"ip_restricted": False}, "IP restriction"),
        ({"can_internal_transfer": True}, "internal transfer"),
        ({"can_universal_transfer": True}, "universal transfer"),
    ],
)
def test_permission_recheck_disables_account_for_unsafe_key_permissions(
    session: Session,
    overrides: dict[str, bool],
    message: str,
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
    probe.snapshot = permission_snapshot(**overrides)

    with pytest.raises(ValueError, match=message):
        account_service.test_connection(
            tenant_id="tenant-a",
            account_id=account.id,
            actor_roles=("tenant_admin",),
        )

    disabled = account_service.list_for_tenant("tenant-a")[0]
    assert disabled.status == "disabled"
    assert disabled.trading_enabled is False


def test_permission_recheck_disables_account_when_binance_rejects_the_key(
    session: Session,
) -> None:
    account_service, backend = service(session)
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
    failing_service = TradingAccountService(session, backend, FailingPermissionProbe())

    with pytest.raises(BinanceConnectorError):
        failing_service.test_connection(
            tenant_id="tenant-a",
            account_id=account.id,
            actor_roles=("tenant_admin",),
        )

    disabled = failing_service.list_for_tenant("tenant-a")[0]
    assert disabled.status == "disabled"
    assert disabled.connection_status == "error"
    assert disabled.trading_enabled is False
    assert all(scope.enabled is False for scope in disabled.scopes)
