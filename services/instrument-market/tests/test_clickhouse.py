from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
from instrument_market.providers.models import PriceLevel, QuoteRecord
from instrument_market.storage.clickhouse import (
    CLICKHOUSE_DDL,
    REQUIRED_TABLES,
    ClickHouseClient,
    quote_row,
)


def test_clickhouse_ddl_contains_required_market_tables() -> None:
    for table in (
        "market_quote_raw",
        "market_history_raw",
        "market_quote",
        "market_minute",
        "market_transaction",
        "market_bar",
        "corporate_action",
        "financial_metric",
        "block_membership_history",
        "ingest_observation",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in CLICKHOUSE_DDL

    assert "ReplacingMergeTree(ingested_at)" in CLICKHOUSE_DDL
    assert "ALTER TABLE market_bar ADD COLUMN IF NOT EXISTS batch_id" in CLICKHOUSE_DDL
    assert CLICKHOUSE_DDL.count("ADD COLUMN IF NOT EXISTS quality_status") >= 2
    assert "PARTITION BY" in CLICKHOUSE_DDL
    assert "ORDER BY" in CLICKHOUSE_DDL


def test_quote_row_preserves_decimal_values_and_source_metadata() -> None:
    source_time = datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC)
    quote = QuoteRecord(
        exchange="SSE",
        symbol="600519",
        source_time=source_time,
        collected_at=source_time,
        last_price=Decimal("1468.20"),
        previous_close=Decimal("1450.21"),
        open_price=Decimal("1458.00"),
        high_price=Decimal("1472.50"),
        low_price=Decimal("1456.80"),
        volume=Decimal("1023400"),
        amount=Decimal("1502340000.00"),
        bids=(PriceLevel(price=Decimal("1468.10"), quantity=Decimal("2300")),),
        asks=(PriceLevel(price=Decimal("1468.30"), quantity=Decimal("1200")),),
        provider="mootdx",
        source_id="tdx-primary",
        payload_hash="sha256:abc",
    )

    row = quote_row(quote)

    assert row["last_price"] == Decimal("1468.20")
    assert row["volume"] == Decimal("1023400")
    assert row["provider"] == "mootdx"
    assert row["source_id"] == "tdx-primary"
    assert row["payload_hash"] == "sha256:abc"


def test_schema_readiness_requires_every_market_table() -> None:
    def complete_schema(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="\n".join(sorted(REQUIRED_TABLES)))

    complete = ClickHouseClient(
        base_url="http://clickhouse.test",
        database="qt_market",
        user="user",
        password="secret",
        transport=httpx.MockTransport(complete_schema),
    )

    assert complete.schema_is_ready() is True
    complete.close()

    def partial_schema(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="market_quote\nmarket_quote_raw\n")

    partial = ClickHouseClient(
        base_url="http://clickhouse.test",
        database="qt_market",
        user="user",
        password="secret",
        transport=httpx.MockTransport(partial_schema),
    )

    assert partial.schema_is_ready() is False
    partial.close()
