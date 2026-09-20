from typing import Any

from instrument_market.services.history import HistoryViewService


class QueryStub:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, str | int] | None]] = []

    def query_json_each_row(self, query, *, parameters=None):
        self.calls.append((query, parameters))
        return self.rows


def test_bar_view_returns_chronological_decimal_strings() -> None:
    client = QueryStub(
        [
            {
                "event_time": "2026-09-18 07:00:00",
                "open": 9.05,
                "high": 9.15,
                "low": 9,
                "close": 9.07,
                "volume": 51759300,
                "amount": 469969408,
                "source_id": "tdx-node",
                "quality_status": "healthy",
            }
        ]
    )

    result = HistoryViewService(client).bars(
        exchange="SSE",
        symbol="600000",
        interval="1d",
        limit=240,
    )

    assert client.calls[0][1] == {
        "exchange": "SSE",
        "symbol": "600000",
        "interval": "1d",
        "limit": 240,
    }
    assert result["coverage"] == "collected"
    assert result["items"][0]["close"] == "9.07"
    assert result["items"][0]["event_time"] == "2026-09-18T07:00:00Z"


def test_empty_minute_view_is_pending() -> None:
    result = HistoryViewService(QueryStub([])).minutes(
        exchange="SZSE",
        symbol="000001",
        trade_date=None,
    )

    assert result == {
        "provider": "mootdx",
        "exchange": "SZSE",
        "symbol": "000001",
        "trade_date": None,
        "coverage": "pending",
        "items": [],
    }


def test_transactions_surface_partial_coverage() -> None:
    client = QueryStub(
        [
            {
                "trade_date": "2026-09-18",
                "event_time": "2026-09-18 01:31:00",
                "price": 9.02,
                "quantity": 300,
                "side": "buy",
                "source_offset": 1,
                "source_id": "tdx-node",
                "quality_status": "partial",
            }
        ]
    )

    result = HistoryViewService(client).transactions(
        exchange="SSE",
        symbol="600000",
        trade_date=None,
        limit=200,
    )

    assert result["coverage"] == "partial"
    assert result["trade_date"] == "2026-09-18"
    assert result["items"][0]["quantity"] == "300"
