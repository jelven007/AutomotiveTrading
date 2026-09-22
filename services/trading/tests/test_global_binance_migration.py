import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0005_global_binance_account.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("global_binance_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_rejects_multiple_existing_account_owners() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE trading_accounts (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id VARCHAR(36) NOT NULL,
                    provider VARCHAR(32) NOT NULL,
                    account_slot VARCHAR(24) NOT NULL,
                    CONSTRAINT uq_trading_accounts_tenant_provider_slot
                        UNIQUE (tenant_id, provider, account_slot)
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO trading_accounts
                    (id, tenant_id, provider, account_slot)
                VALUES
                    ('one', 'tenant-a', 'binance', 'primary'),
                    ('two', 'tenant-b', 'binance', 'primary')
                """
            )
        )
        context = MigrationContext.configure(connection)

        with (
            pytest.raises(RuntimeError, match="multiple Binance account owners"),
            Operations.context(context),
        ):
            load_migration().upgrade()

        count = connection.scalar(sa.text("SELECT COUNT(*) FROM trading_accounts"))
        assert count == 2
