from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from instrument_market.services.history import HistoryIngestionService


class RecordingSink:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, list[dict[str, Any]]]] = []

    def insert_json_each_row(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.inserts.append((table, rows))


def batch(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "batch_id": f"{dataset}-batch",
        "exchange": "SSE",
        "symbol": "600000",
        "trade_date": "2026-09-18",
        "source_id": "tdx-node",
        "collected_at": datetime(2026, 9, 20, 1, 31, tzinfo=UTC),
        "rows": rows,
        "metadata": {"complete": True, "volunit": 100},
    }


def test_daily_bar_ingestion_persists_raw_before_scaled_standard_rows() -> None:
    sink = RecordingSink()
    service = HistoryIngestionService(sink)
    payload = batch(
        "bar",
        [
            {
                "datetime": "2026-09-18 15:00",
                "open": 9.05,
                "high": 9.15,
                "low": 9,
                "close": 9.07,
                "vol": 517593,
                "amount": 469969408,
            }
        ],
    )
    payload["metadata"].update(interval="1d", adjustment="none")

    result = service.ingest(**payload)

    assert [table for table, _ in sink.inserts] == ["market_history_raw", "market_bar"]
    row = sink.inserts[1][1][0]
    assert row["event_time"] == datetime(2026, 9, 18, 7, 0, tzinfo=UTC)
    assert row["volume"] == Decimal("51759300")
    assert row["quality_status"] == "healthy"
    assert result["accepted"] == 1


def test_minute_ingestion_uses_explicit_source_time_and_volume_unit() -> None:
    sink = RecordingSink()
    payload = batch(
        "minute",
        [
            {
                "datetime": "2026-09-18T01:31:00+00:00",
                "price": 9.02,
                "vol": 13604,
                "source_offset": 0,
            }
        ],
    )

    result = HistoryIngestionService(sink).ingest(**payload)

    assert [table for table, _ in sink.inserts] == ["market_history_raw", "market_minute"]
    row = sink.inserts[1][1][0]
    assert row["event_time"] == datetime(2026, 9, 18, 1, 31, tzinfo=UTC)
    assert row["volume"] == Decimal("1360400")
    assert result["rejected"] == 0


def test_transaction_ingestion_keeps_invalid_rows_only_in_raw() -> None:
    sink = RecordingSink()
    payload = batch(
        "transaction",
        [
            {
                "time": "09:31",
                "price": 9.02,
                "vol": 3,
                "buyorsell": 0,
                "source_offset": 0,
            },
            {
                "time": "15:14",
                "price": 9.07,
                "vol": 9,
                "buyorsell": 5,
                "source_offset": 1,
            },
        ],
    )

    result = HistoryIngestionService(sink).ingest(**payload)

    assert len(sink.inserts[0][1]) == 2
    assert len(sink.inserts[1][1]) == 1
    assert sink.inserts[1][1][0]["side"] == "buy"
    assert sink.inserts[1][1][0]["quantity"] == Decimal("300")
    assert result["received"] == 2
    assert result["accepted"] == 1
    assert result["rejected"] == 1
    assert result["coverage"] == "partial"


def test_history_ingestion_rejects_wrong_dataset() -> None:
    with pytest.raises(ValueError, match="unsupported history dataset"):
        HistoryIngestionService(RecordingSink()).ingest(**batch("quote", [{}]))
