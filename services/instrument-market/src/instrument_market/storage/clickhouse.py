from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from instrument_market.pipeline.envelope import RawEnvelope
from instrument_market.providers.models import PriceLevel, ProviderName, QuoteRecord

REQUIRED_TABLES = frozenset(
    {
        "market_quote_raw",
        "market_quote",
        "market_transaction",
        "market_bar",
        "corporate_action",
        "financial_metric",
        "block_membership_history",
        "ingest_observation",
    }
)

CLICKHOUSE_DDL = """
CREATE TABLE IF NOT EXISTS market_quote_raw (
    event_id UUID,
    exchange LowCardinality(String),
    symbol String,
    source_time DateTime64(3, 'UTC'),
    collected_at DateTime64(3, 'UTC'),
    provider LowCardinality(String),
    source_id String,
    payload_hash FixedString(71),
    payload String
) ENGINE = MergeTree
PARTITION BY toDate(collected_at)
ORDER BY (exchange, symbol, source_time, collected_at);

CREATE TABLE IF NOT EXISTS market_quote (
    exchange LowCardinality(String),
    symbol String,
    source_time DateTime64(3, 'UTC'),
    collected_at DateTime64(3, 'UTC'),
    last_price Decimal(20, 6),
    previous_close Decimal(20, 6),
    open_price Decimal(20, 6),
    high_price Decimal(20, 6),
    low_price Decimal(20, 6),
    volume Decimal(28, 4),
    amount Decimal(28, 4),
    bids String,
    asks String,
    provider LowCardinality(String),
    source_id String,
    payload_hash String,
    quality_status LowCardinality(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(source_time)
ORDER BY (exchange, symbol, source_time);

CREATE TABLE IF NOT EXISTS market_transaction (
    exchange LowCardinality(String),
    symbol String,
    event_time DateTime64(3, 'UTC'),
    price Decimal(20, 6),
    quantity Decimal(28, 4),
    side LowCardinality(String),
    source_offset UInt32,
    provider LowCardinality(String),
    source_id String,
    payload_hash String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toDate(event_time)
ORDER BY (exchange, symbol, event_time, source_offset);

CREATE TABLE IF NOT EXISTS market_bar (
    exchange LowCardinality(String),
    symbol String,
    interval LowCardinality(String),
    adjustment LowCardinality(String),
    event_time DateTime64(3, 'UTC'),
    open Decimal(20, 6),
    high Decimal(20, 6),
    low Decimal(20, 6),
    close Decimal(20, 6),
    volume Decimal(28, 4),
    amount Decimal(28, 4),
    provider LowCardinality(String),
    payload_hash String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(event_time)
ORDER BY (exchange, symbol, interval, adjustment, event_time);

CREATE TABLE IF NOT EXISTS corporate_action (
    exchange LowCardinality(String),
    symbol String,
    event_date Date,
    category LowCardinality(String),
    payload String,
    provider LowCardinality(String),
    payload_hash String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(event_date)
ORDER BY (exchange, symbol, event_date, category);

CREATE TABLE IF NOT EXISTS financial_metric (
    symbol String,
    report_date Date,
    metric_id UInt16,
    metric_name String,
    metric_value Decimal(32, 8),
    provider LowCardinality(String),
    payload_hash String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (symbol, report_date, metric_id);

CREATE TABLE IF NOT EXISTS block_membership_history (
    block_code String,
    block_name String,
    symbol String,
    valid_from DateTime64(3, 'UTC'),
    valid_to Nullable(DateTime64(3, 'UTC')),
    provider LowCardinality(String),
    payload_hash String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(valid_from)
ORDER BY (block_code, symbol, valid_from);

CREATE TABLE IF NOT EXISTS ingest_observation (
    dataset LowCardinality(String),
    shard_id String,
    observed_at DateTime64(3, 'UTC'),
    expected_count UInt32,
    received_count UInt32,
    empty_count UInt32,
    duration_ms UInt32,
    source_id String,
    status LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY toDate(observed_at)
ORDER BY (dataset, observed_at, shard_id);
""".strip()


def _provider_value(provider: ProviderName | str) -> str:
    return provider.value if isinstance(provider, ProviderName) else provider


def _levels_json(levels: tuple[PriceLevel, ...]) -> str:
    return json.dumps(
        [{"price": str(level.price), "quantity": str(level.quantity)} for level in levels],
        separators=(",", ":"),
    )


def quote_row(quote: QuoteRecord) -> dict[str, Any]:
    return {
        "exchange": quote.exchange,
        "symbol": quote.symbol,
        "source_time": quote.source_time.astimezone(UTC),
        "collected_at": quote.collected_at.astimezone(UTC),
        "last_price": quote.last_price,
        "previous_close": quote.previous_close,
        "open_price": quote.open_price,
        "high_price": quote.high_price,
        "low_price": quote.low_price,
        "volume": quote.volume,
        "amount": quote.amount,
        "bids": _levels_json(quote.bids),
        "asks": _levels_json(quote.asks),
        "provider": _provider_value(quote.provider),
        "source_id": quote.source_id,
        "payload_hash": quote.payload_hash,
    }


def raw_quote_row(envelope: RawEnvelope) -> dict[str, Any]:
    return {
        "event_id": envelope.event_id,
        "exchange": envelope.exchange,
        "symbol": envelope.symbol,
        "source_time": envelope.source_time,
        "collected_at": envelope.collected_at,
        "provider": envelope.provider.value,
        "source_id": envelope.source_id,
        "payload_hash": envelope.payload_hash,
        "payload": json.dumps(
            asdict(envelope)["payload"],
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        ),
    }


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    raise TypeError(f"unsupported ClickHouse value: {type(value).__name__}")


class ClickHouseClient:
    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        user: str,
        password: str,
        timeout_seconds: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.database = database
        self.http = httpx.Client(
            base_url=base_url,
            auth=(user, password),
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self.http.close()

    def ping(self) -> bool:
        response = self.http.get("/ping")
        return response.status_code == 200 and response.text.strip() == "Ok."

    def schema_is_ready(self) -> bool:
        response = self.http.post(
            "/",
            params={"database": self.database},
            content=(
                f"SELECT name FROM system.tables WHERE database = '{self.database}' FORMAT TSV"
            ).encode(),
        )
        response.raise_for_status()
        return set(response.text.splitlines()) >= REQUIRED_TABLES

    def initialize(self) -> None:
        for statement in CLICKHOUSE_DDL.split(";\n"):
            sql = statement.strip()
            if sql:
                self.execute(sql)

    def execute(self, query: str) -> None:
        response = self.http.post(
            "/",
            params={"database": self.database},
            content=query.encode(),
        )
        response.raise_for_status()

    def insert_json_each_row(
        self,
        table: str,
        rows: Iterable[Mapping[str, Any]],
    ) -> None:
        payload = "\n".join(
            json.dumps(
                dict(row),
                ensure_ascii=False,
                separators=(",", ":"),
                default=_json_default,
            )
            for row in rows
        )
        if not payload:
            return
        response = self.http.post(
            "/",
            params={
                "database": self.database,
                "query": f"INSERT INTO {table} FORMAT JSONEachRow",
            },
            content=payload.encode(),
        )
        response.raise_for_status()
