"""Add AES-GCM credential metadata and active account state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_local_binance_credentials"
down_revision: str | None = "0002_binance_key_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trading_accounts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("trading_accounts", sa.Column("credential_version", sa.Integer()))
    op.add_column("trading_accounts", sa.Column("credential_confirmed_at", sa.DateTime()))
    op.add_column("trading_accounts", sa.Column("credential_confirmed_by", sa.String(36)))
    op.add_column(
        "local_encrypted_secrets",
        sa.Column("nonce", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "local_encrypted_secrets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("local_encrypted_secrets", "version")
    op.drop_column("local_encrypted_secrets", "nonce")
    op.drop_column("trading_accounts", "credential_confirmed_by")
    op.drop_column("trading_accounts", "credential_confirmed_at")
    op.drop_column("trading_accounts", "credential_version")
    op.drop_column("trading_accounts", "is_active")
