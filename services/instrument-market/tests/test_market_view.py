from __future__ import annotations

import json
from typing import Any

from instrument_market.services.market_view import MarketViewService


class QueryStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str | int] | None]] = []

    def query_json_each_row(
        self,
        query: str,
        *,
        parameters: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((query, parameters))
        if "market_quote" in query:
            return [
                {
                    "exchange": "SSE",
                    "symbol": "600000",
                    "name": "浦发银行\x00",
                    "source_time": "2026-09-18 15:00:00",
                    "collected_at": "2026-09-20 01:31:03",
                    "last_price": 10.5,
                    "previous_close": 10,
                    "open_price": 10.1,
                    "high_price": 10.8,
                    "low_price": 9.9,
                    "volume": 1200,
                    "amount": 12600,
                    "quality_status": "stale",
                    "quality_reasons": '["trade_date_unverified"]',
                    "source_id": "tdx-node",
                    "available": 1,
                }
            ]
        return [
            {
                "body": json.dumps(
                    {
                        "observed_at": "2026-09-20T01:31:04+00:00",
                        "duration_ms": 2310,
                        "universe_verification": "unverified",
                        "markets": {
                            "SSE": {
                                "expected": 1,
                                "received": 1,
                                "missing": [],
                                "source_error": None,
                                "universe_complete": True,
                            },
                            "SZSE": {
                                "expected": 1,
                                "received": 1,
                                "missing": [],
                                "source_error": None,
                                "universe_complete": True,
                            },
                            "BSE": {
                                "expected": 0,
                                "received": 0,
                                "missing": [],
                                "source_error": "bse_protocol_unsupported",
                                "universe_complete": False,
                            },
                        },
                    }
                )
            }
        ]


def test_market_view_returns_real_quote_fields_and_sse_szse_coverage() -> None:
    client = QueryStub()
    result = MarketViewService(client).latest_quotes(limit=6000)

    assert client.calls[0][1] == {"limit": 6000}
    assert "exchange IN ('SSE', 'SZSE')" in client.calls[0][0]
    assert result["scope"] == ["SSE", "SZSE"]
    assert result["available"] == 1
    assert result["quality"] == {"stale": 1}
    assert result["items"][0] == {
        "exchange": "SSE",
        "symbol": "600000",
        "name": "浦发银行",
        "source_time": "2026-09-18T15:00:00Z",
        "collected_at": "2026-09-20T01:31:03Z",
        "last_price": "10.5",
        "previous_close": "10",
        "change_percent": "5.00",
        "open_price": "10.1",
        "high_price": "10.8",
        "low_price": "9.9",
        "volume": "1200",
        "amount": "12600",
        "quality_status": "stale",
        "quality_reasons": ["trade_date_unverified"],
        "source_id": "tdx-node",
    }
    assert result["coverage"] == {
        "status": "collected",
        "expected": 2,
        "received": 2,
        "missing": 0,
        "duration_ms": 2310,
        "observed_at": "2026-09-20T01:31:04+00:00",
        "verification": "unverified",
        "markets": {
            "SSE": {
                "expected": 1,
                "received": 1,
                "missing": [],
                "source_error": None,
                "universe_complete": True,
            },
            "SZSE": {
                "expected": 1,
                "received": 1,
                "missing": [],
                "source_error": None,
                "universe_complete": True,
            },
        },
    }
