"""Enforce one Binance account slot for the whole system."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_global_binance_account"
down_revision: str | None = "0004_single_binance_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT provider, account_slot
                FROM trading_accounts
                WHERE provider = 'binance'
                GROUP BY provider, account_slot
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError("multiple Binance account owners must be resolved before migration")

    with op.batch_alter_table("trading_accounts") as batch:
        batch.drop_constraint(
            "uq_trading_accounts_tenant_provider_slot",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_trading_accounts_provider_slot",
            ["provider", "account_slot"],
        )


def downgrade() -> None:
    with op.batch_alter_table("trading_accounts") as batch:
        batch.drop_constraint(
            "uq_trading_accounts_provider_slot",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_trading_accounts_tenant_provider_slot",
            ["tenant_id", "provider", "account_slot"],
        )
