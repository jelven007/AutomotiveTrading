import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0002_single_system_owner.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("single_owner_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_users_table(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                created_at DATETIME NOT NULL
            )
            """
        )
    )


def test_migration_backfills_existing_owner() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        create_users_table(connection)
        connection.execute(
            sa.text("INSERT INTO users (id, created_at) VALUES ('user-a', '2026-09-22 00:00:00')")
        )
        context = MigrationContext.configure(connection)

        with Operations.context(context):
            load_migration().upgrade()

        owner = connection.execute(sa.text("SELECT slot, user_id FROM system_owners")).one()
        assert owner == ("primary", "user-a")


def test_migration_rejects_multiple_existing_users() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        create_users_table(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO users (id, created_at)
                VALUES
                    ('user-a', '2026-09-22 00:00:00'),
                    ('user-b', '2026-09-22 00:00:01')
                """
            )
        )
        context = MigrationContext.configure(connection)

        with (
            pytest.raises(RuntimeError, match="multiple users"),
            Operations.context(context),
        ):
            load_migration().upgrade()

        inspector = sa.inspect(connection)
        assert "system_owners" not in inspector.get_table_names()
