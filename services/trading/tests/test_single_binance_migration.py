import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from trading.binance_account import BinanceAccountReplaceCommand
from trading.models import (
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingProvider,
)

MIGRATION_PATH = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0004_single_binance_account.py"
)


def account(*, tenant_id: str, alias: str) -> TradingAccount:
    return TradingAccount(
        tenant_id=tenant_id,
        alias=alias,
        market_group=MarketGroup.BINANCE,
        provider=TradingProvider.BINANCE,
        account_slot="primary",
        environment="production",
        credential_type=CredentialType.HMAC,
        status=AccountStatus.READ_ONLY,
        connection_status=ConnectionStatus.CONNECTED,
        trading_enabled=False,
        created_by="user-a",
    )


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("single_binance_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_allows_only_one_binance_slot_per_tenant(session: Session) -> None:
    session.add_all(
        [
            account(
                tenant_id="tenant-a",
                alias="first",
            ),
            account(
                tenant_id="tenant-a",
                alias="second",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_model_allows_one_binance_account_for_each_tenant(session: Session) -> None:
    session.add_all(
        [
            account(
                tenant_id="tenant-a",
                alias="first",
            ),
            account(
                tenant_id="tenant-b",
                alias="second",
            ),
        ]
    )

    session.commit()


def test_migration_rejects_existing_duplicate_binance_accounts() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE trading_accounts (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL,
                    alias VARCHAR(120) NOT NULL,
                    provider VARCHAR(32) NOT NULL
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO trading_accounts (id, tenant_id, alias, provider)
                VALUES
                    ('one', 'tenant-a', 'first', 'binance'),
                    ('two', 'tenant-a', 'second', 'binance')
                """
            )
        )
        context = MigrationContext.configure(connection)

        with (
            pytest.raises(RuntimeError, match="duplicate Binance accounts"),
            Operations.context(context),
        ):
            load_migration().upgrade()

        count = connection.scalar(sa.text("SELECT COUNT(*) FROM trading_accounts"))
        assert count == 2


def test_replace_contract_accepts_only_hmac_key_and_secret() -> None:
    command = BinanceAccountReplaceCommand(
        alias="primary",
        api_key="key",
        api_secret="secret",
        ip_whitelist_confirmed=True,
    )

    assert command.api_key.get_secret_value() == "key"
    with pytest.raises(ValidationError):
        BinanceAccountReplaceCommand(
            alias="primary",
            api_key="key",
            api_secret="secret",
            ip_whitelist_confirmed=True,
            credential_type="ed25519",
        )
