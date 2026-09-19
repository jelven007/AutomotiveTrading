"""Create tenant-isolated managed secret records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_kms_secrets"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "managed_secrets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("key_id", sa.String(512)),
        sa.Column("encrypted_data_key", sa.LargeBinary()),
        sa.Column("nonce", sa.LargeBinary()),
        sa.Column("ciphertext", sa.LargeBinary()),
        sa.Column("encryption_context_json", sa.Text()),
        sa.Column("purpose", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("ix_managed_secrets_tenant_id", "managed_secrets", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("managed_secrets")
