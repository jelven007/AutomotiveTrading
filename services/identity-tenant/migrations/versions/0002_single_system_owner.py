"""Enforce a single system owner in production registration mode."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002_single_system_owner"
down_revision: str | None = "0001_identity_tenant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    existing_users = connection.execute(
        sa.text("SELECT id FROM users ORDER BY created_at, id LIMIT 2")
    ).all()
    if len(existing_users) > 1:
        raise RuntimeError("multiple users must be resolved before enabling single-owner mode")

    op.create_table(
        "system_owners",
        sa.Column("slot", sa.String(24), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    if existing_users:
        connection.execute(
            sa.text(
                """
                INSERT INTO system_owners (slot, user_id, created_at)
                VALUES (:slot, :user_id, :created_at)
                """
            ),
            {
                "slot": "primary",
                "user_id": existing_users[0][0],
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            },
        )


def downgrade() -> None:
    op.drop_table("system_owners")
