"""Create risk policy, evaluation, approval, and snapshot tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_risk_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("policy_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "version"),
    )
    op.create_index("ix_risk_policies_tenant_id", "risk_policies", ["tenant_id"])

    op.create_table(
        "risk_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("order_fingerprint", sa.String(64), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_risk_evaluations_tenant_id",
        "risk_evaluations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_risk_evaluations_account_id",
        "risk_evaluations",
        ["account_id"],
    )

    op.create_table(
        "risk_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("evaluation_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("order_fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_risk_approvals_tenant_id", "risk_approvals", ["tenant_id"])
    op.create_index("ix_risk_approvals_account_id", "risk_approvals", ["account_id"])
    op.create_index(
        "ix_risk_approvals_evaluation_id",
        "risk_approvals",
        ["evaluation_id"],
    )

    op.create_table(
        "risk_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("account_scope", sa.String(32), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_risk_snapshots_tenant_id", "risk_snapshots", ["tenant_id"])
    op.create_index("ix_risk_snapshots_account_id", "risk_snapshots", ["account_id"])


def downgrade() -> None:
    op.drop_table("risk_snapshots")
    op.drop_table("risk_approvals")
    op.drop_table("risk_evaluations")
    op.drop_table("risk_policies")
