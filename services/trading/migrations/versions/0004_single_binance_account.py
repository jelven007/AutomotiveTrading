"""Enforce one Binance account slot per tenant."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_single_binance_account"
down_revision: str | None = "0003_local_binance_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT tenant_id
            FROM trading_accounts
            WHERE provider = 'binance'
            GROUP BY tenant_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError("duplicate Binance accounts must be resolved before migration")

    with op.batch_alter_table("trading_accounts") as batch:
        batch.add_column(sa.Column("account_slot", sa.String(24), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE trading_accounts
            SET account_slot = 'primary'
            WHERE provider = 'binance'
            """
        )
    )

    with op.batch_alter_table("trading_accounts") as batch:
        batch.create_check_constraint(
            "ck_trading_accounts_binance_slot",
            "(provider = 'binance' AND account_slot = 'primary') "
            "OR (provider <> 'binance' AND account_slot IS NULL)",
        )
        batch.create_unique_constraint(
            "uq_trading_accounts_tenant_provider_slot",
            ["tenant_id", "provider", "account_slot"],
        )


def downgrade() -> None:
    with op.batch_alter_table("trading_accounts") as batch:
        batch.drop_constraint(
            "uq_trading_accounts_tenant_provider_slot",
            type_="unique",
        )
        batch.drop_constraint(
            "ck_trading_accounts_binance_slot",
            type_="check",
        )
        batch.drop_column("account_slot")
