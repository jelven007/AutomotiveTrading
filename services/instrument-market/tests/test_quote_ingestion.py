from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from instrument_market.services.quotes import QuoteIngestionService


class RecordingSink:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, list[dict[str, Any]]]] = []

    def insert_json_each_row(
        self,
        table: str,
        rows: list[dict[str, Any]],
    ) -> None:
        self.inserts.append((table, rows))


def test_quote_ingestion_persists_raw_before_canonical_rows() -> None:
    sink = RecordingSink()
    service = QuoteIngestionService(sink, stale_after_seconds=3)
    collected_at = datetime(2026, 9, 20, 1, 31, 3, tzinfo=UTC)

    result = service.ingest(
        batch_id="batch-1",
        exchange="SSE",
        trade_date="2026-09-20",
        source_id="tdx-primary",
        collected_at=collected_at,
        payloads=[
            {
                "code": "600519",
                "price": 1468.2,
                "last_close": 1450.21,
                "open": 1458.0,
                "high": 1472.5,
                "low": 1456.8,
                "vol": 1023400,
                "amount": 1502340000.0,
                "bid1": 1468.1,
                "bid_vol1": 2300,
                "ask1": 1468.3,
                "ask_vol1": 1200,
                "servertime": "09:31:02",
            }
        ],
    )

    assert [table for table, _ in sink.inserts] == ["market_quote_raw", "market_quote"]
    assert sink.inserts[0][1][0]["payload_hash"].startswith("sha256:")
    assert sink.inserts[1][1][0]["quality_status"] == "healthy"
    assert result == {
        "batch_id": "batch-1",
        "accepted": 1,
        "quality": {"healthy": 1},
    }


def test_quote_ingestion_keeps_invalid_quote_with_quality_status() -> None:
    sink = RecordingSink()
    service = QuoteIngestionService(sink, stale_after_seconds=3)
    collected_at = datetime(2026, 9, 20, 1, 31, 3, tzinfo=UTC)

    result = service.ingest(
        batch_id="batch-2",
        exchange="SSE",
        trade_date="2026-09-20",
        source_id="tdx-primary",
        collected_at=collected_at,
        payloads=[
            {
                "code": "600000",
                "price": -1,
                "last_close": 10,
                "open": 10,
                "high": 10,
                "low": 10,
                "vol": 1,
                "amount": 1,
                "servertime": "09:31:02",
            }
        ],
    )

    assert sink.inserts[1][1][0]["quality_status"] == "invalid"
    assert result["quality"] == {"invalid": 1}
