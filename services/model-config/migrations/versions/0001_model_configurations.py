"""Create model configuration tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_model_configurations"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("secret_ref", sa.String(160), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("temperature", sa.String(16), nullable=False),
        sa.Column("top_p", sa.String(16), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("rpm_limit", sa.Integer(), nullable=False),
        sa.Column("daily_token_limit", sa.Integer(), nullable=False),
        sa.Column("daily_cost_limit", sa.String(32), nullable=False),
        sa.Column("allowed_environments_json", sa.Text(), nullable=False),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index(
        "ix_model_configurations_tenant_id",
        "model_configurations",
        ["tenant_id"],
    )
    op.create_table(
        "strategy_model_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "configuration_id",
            sa.String(36),
            sa.ForeignKey("model_configurations.id"),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(36), nullable=False),
        sa.UniqueConstraint("tenant_id", "configuration_id", "strategy_id"),
    )
    op.create_index(
        "ix_strategy_model_references_tenant_id",
        "strategy_model_references",
        ["tenant_id"],
    )
    op.create_index(
        "ix_strategy_model_references_configuration_id",
        "strategy_model_references",
        ["configuration_id"],
    )


def downgrade() -> None:
    op.drop_table("strategy_model_references")
    op.drop_table("model_configurations")
