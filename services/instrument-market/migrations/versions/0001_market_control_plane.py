"""Create market data control-plane tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_market_control_plane"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("completeness", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "market", "dataset"),
    )
    op.create_table(
        "collector_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("shard_id", sa.String(64), nullable=False),
        sa.Column("schedule", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_started_at", sa.DateTime()),
        sa.Column("last_completed_at", sa.DateTime()),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("ix_collector_jobs_dataset", "collector_jobs", ["dataset"])
    op.create_table(
        "collector_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("shard_id", sa.String(64), nullable=False),
        sa.Column("cursor_key", sa.String(160), nullable=False),
        sa.Column("cursor_value", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dataset", "shard_id", "cursor_key"),
    )
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(16)),
        sa.Column("symbol", sa.String(32)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
    )
    op.create_index(
        "ix_data_quality_issues_dataset",
        "data_quality_issues",
        ["dataset"],
    )
    op.create_table(
        "raw_object_manifests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("bucket", sa.String(128), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("bucket", "object_key", "content_hash"),
    )


def downgrade() -> None:
    op.drop_table("raw_object_manifests")
    op.drop_table("data_quality_issues")
    op.drop_table("collector_checkpoints")
    op.drop_table("collector_jobs")
    op.drop_table("provider_capabilities")
