from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from instrument_market.errors import ServiceError
from instrument_market.services.quotes import QuoteIngestionService
from instrument_market.storage.receipts import ReceiptStore, metadata
from sqlalchemy import create_engine


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
    collected_at = datetime(2026, 9, 20, 1, 31, 3, tzinfo=UTC)
    service = QuoteIngestionService(sink, stale_after_seconds=3, clock=lambda: collected_at)

    result = service.ingest(
        batch_id="batch-1",
        exchange="SSE",
        trade_date="2026-09-20",
        source_id="tdx-primary",
        collected_at=collected_at,
        metadata={"trade_date_basis": "verified", "instruments": {"600519": {"volunit": 1}}},
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
        "received": 1,
        "rejected": 0,
        "errors": [],
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


def historical_batch() -> dict[str, Any]:
    return {
        "batch_id": "history-1",
        "exchange": "SSE",
        "trade_date": "2020-01-02",
        "source_id": "tdx-test",
        "collected_at": datetime(2020, 1, 2, 1, 31, 3, tzinfo=UTC),
        "payloads": [{"code": "600000", "price": 10, "servertime": "09:31:02"}],
    }


def test_quote_ingestion_replay_uses_current_receive_time() -> None:
    service = QuoteIngestionService(RecordingSink(), stale_after_seconds=3)
    result = service.ingest(**historical_batch())
    assert result["quality"] == {"stale": 1}


def test_quote_ingestion_bad_row_keeps_raw_and_valid_neighbor() -> None:
    sink = RecordingSink()
    batch = historical_batch()
    batch["payloads"].append({"code": "600001", "price": "broken"})
    result = QuoteIngestionService(sink, stale_after_seconds=3).ingest(**batch)
    assert len(sink.inserts[0][1]) == 2
    assert result["accepted"] == 1
    assert result["rejected"] == 1


def test_quote_ingestion_repeated_batch_does_not_write_again() -> None:
    sink = RecordingSink()
    service = QuoteIngestionService(sink, stale_after_seconds=3)
    result = service.ingest(**historical_batch())
    assert service.ingest(**historical_batch()) == result
    assert len(sink.inserts) == 2


def test_receipt_survives_service_restart_and_rejects_conflict(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'receipts.db'}")
    metadata.create_all(engine)
    sink = RecordingSink()
    original = QuoteIngestionService(sink, stale_after_seconds=3, receipts=ReceiptStore(engine))
    result = original.ingest(**historical_batch())
    restarted = QuoteIngestionService(sink, stale_after_seconds=3, receipts=ReceiptStore(engine))
    assert restarted.ingest(**historical_batch()) == result
    assert len(sink.inserts) == 2
    conflict = historical_batch()
    conflict["payloads"][0]["price"] = 11
    with pytest.raises(ServiceError) as error:
        restarted.ingest(**conflict)
    assert error.value.status_code == 409
    assert len(sink.inserts) == 2
    engine.dispose()


def test_standard_write_failure_replays_with_same_raw_event_id() -> None:
    class FailingSink(RecordingSink):
        fail = True

        def insert_json_each_row(self, table, rows):
            if table == "market_quote" and self.fail:
                self.fail = False
                raise ConnectionError("simulated")
            super().insert_json_each_row(table, rows)

    sink = FailingSink()
    service = QuoteIngestionService(sink, stale_after_seconds=3)
    with pytest.raises(ConnectionError, match="simulated"):
        service.ingest(**historical_batch())
    assert service.ingest(**historical_batch())["accepted"] == 1
    raw = [rows[0] for table, rows in sink.inserts if table == "market_quote_raw"]
    assert len(raw) == 2
    assert raw[0]["event_id"] == raw[1]["event_id"]


def test_unexpected_market_and_duplicate_are_retained_only_in_raw() -> None:
    batch = historical_batch()
    batch["payloads"] += [
        {"code": "600000", "price": 10},
        {"code": "600001", "price": 10, "market": 0},
        {"code": "600839", "price": 10, "market": 1},
    ]
    batch["metadata"] = {"requested": ["600000", "600001"]}
    sink = RecordingSink()
    result = QuoteIngestionService(sink, stale_after_seconds=3).ingest(**batch)
    assert len(sink.inserts[0][1]) == 4
    assert result["accepted"] == 1
    assert result["rejected"] == 3
