"""Create trading account, scope, order, kill switch, and local secret tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_trading_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trading_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("alias", sa.String(120), nullable=False),
        sa.Column("market_group", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("environment", sa.String(24), nullable=False),
        sa.Column("external_account_ref", sa.String(160)),
        sa.Column("credential_type", sa.String(24)),
        sa.Column("api_key_fingerprint", sa.String(80)),
        sa.Column("secret_ref", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("connection_status", sa.String(32), nullable=False),
        sa.Column("trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False),
        sa.Column("can_spot_trade", sa.Boolean(), nullable=False),
        sa.Column("can_margin_trade", sa.Boolean(), nullable=False),
        sa.Column("can_futures_trade", sa.Boolean(), nullable=False),
        sa.Column("can_withdraw", sa.Boolean(), nullable=False),
        sa.Column("last_permission_check_at", sa.DateTime()),
        sa.Column("last_synced_at", sa.DateTime()),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "provider", "alias"),
    )
    op.create_index("ix_trading_accounts_tenant_id", "trading_accounts", ["tenant_id"])

    op.create_table(
        "trading_account_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("trading_accounts.id"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_key", sa.String(80), nullable=False),
        sa.Column("symbol", sa.String(40)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("position_mode", sa.String(24)),
        sa.Column("margin_mode", sa.String(24)),
        sa.Column("leverage_limit", sa.Integer()),
        sa.Column("last_synced_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "account_id", "scope_type", "scope_key"),
    )
    op.create_index(
        "ix_trading_account_scopes_tenant_id",
        "trading_account_scopes",
        ["tenant_id"],
    )
    op.create_index(
        "ix_trading_account_scopes_account_id",
        "trading_account_scopes",
        ["account_id"],
    )

    op.create_table(
        "trading_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("trading_accounts.id"),
            nullable=False,
        ),
        sa.Column("client_order_id", sa.String(64), nullable=False),
        sa.Column("broker_order_id", sa.String(80)),
        sa.Column("account_scope", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("position_side", sa.String(8)),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("time_in_force", sa.String(8)),
        sa.Column("quantity", sa.String(40), nullable=False),
        sa.Column("limit_price", sa.String(40)),
        sa.Column("reduce_only", sa.Boolean(), nullable=False),
        sa.Column("margin_side_effect", sa.String(32), nullable=False),
        sa.Column("filled_quantity", sa.String(40), nullable=False),
        sa.Column("average_price", sa.String(40)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("cancel_idempotency_key", sa.String(80)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
        sa.UniqueConstraint("tenant_id", "cancel_idempotency_key"),
        sa.UniqueConstraint("tenant_id", "account_id", "client_order_id"),
    )
    op.create_index("ix_trading_orders_tenant_id", "trading_orders", ["tenant_id"])
    op.create_index("ix_trading_orders_account_id", "trading_orders", ["account_id"])

    op.create_table(
        "trading_kill_switches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("activated_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "scope"),
    )
    op.create_index(
        "ix_trading_kill_switches_tenant_id",
        "trading_kill_switches",
        ["tenant_id"],
    )

    op.create_table(
        "trading_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("trading_accounts.id"),
            nullable=False,
        ),
        sa.Column("operation_type", sa.String(40), nullable=False),
        sa.Column("account_scope", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(40)),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("broker_reference", sa.String(120)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
    )
    op.create_index(
        "ix_trading_operations_tenant_id",
        "trading_operations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_trading_operations_account_id",
        "trading_operations",
        ["account_id"],
    )

    op.create_table(
        "local_encrypted_secrets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_local_encrypted_secrets_tenant_id",
        "local_encrypted_secrets",
        ["tenant_id"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("publish_attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])
    op.create_index(
        "ix_outbox_events_aggregate_id",
        "outbox_events",
        ["aggregate_id"],
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("local_encrypted_secrets")
    op.drop_table("trading_operations")
    op.drop_table("trading_kill_switches")
    op.drop_table("trading_orders")
    op.drop_table("trading_account_scopes")
    op.drop_table("trading_accounts")
