"""Persist ingestion acknowledgments."""

from alembic import op
from instrument_market.storage.receipts import metadata

revision = "0002_ingest_receipts"
down_revision = "0001_market_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    metadata.drop_all(op.get_bind())
