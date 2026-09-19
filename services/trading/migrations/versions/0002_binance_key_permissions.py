"""Persist Binance API key restriction state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_binance_key_permissions"
down_revision: str | None = "0001_trading_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trading_accounts",
        sa.Column("ip_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "trading_accounts",
        sa.Column(
            "can_internal_transfer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "trading_accounts",
        sa.Column(
            "can_universal_transfer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "trading_accounts",
        sa.Column("trading_authority_expiration_time_ms", sa.BigInteger()),
    )
    # 旧记录没有独立权限证据。升级后必须重新校验才能启用交易。
    op.execute(
        sa.text(
            """
            UPDATE trading_accounts
            SET last_permission_check_at = NULL,
                trading_enabled = false,
                status = CASE WHEN status = 'active' THEN 'read_only' ELSE status END
            WHERE provider = 'binance'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("trading_accounts", "trading_authority_expiration_time_ms")
    op.drop_column("trading_accounts", "can_universal_transfer")
    op.drop_column("trading_accounts", "can_internal_transfer")
    op.drop_column("trading_accounts", "ip_restricted")
