"""Create immutable audit records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_audit_records"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("before_ref", sa.String(512), nullable=True),
        sa.Column("after_ref", sa.String(512), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("tenant_id", "sequence"),
    )
    op.create_index("ix_audit_records_event_id", "audit_records", ["event_id"])
    op.create_index("ix_audit_records_tenant_id", "audit_records", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("audit_records")
