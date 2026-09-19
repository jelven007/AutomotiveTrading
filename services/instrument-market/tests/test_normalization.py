from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from instrument_market.pipeline.deduplicate import bar_key, quote_key, transaction_key
from instrument_market.pipeline.normalize import normalize_quote


def test_normalize_quote_maps_mootdx_fields_without_float_rounding() -> None:
    collected_at = datetime(2026, 9, 20, 1, 31, 2, 412000, tzinfo=UTC)

    quote = normalize_quote(
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
        },
        exchange="SSE",
        trade_date="2026-09-20",
        collected_at=collected_at,
    )

    assert quote.symbol == "600519"
    assert quote.last_price == Decimal("1468.2")
    assert quote.volume == Decimal("1023400")
    assert quote.bids[0].price == Decimal("1468.1")
    assert quote.asks[0].quantity == Decimal("1200")
    assert quote.source_time == datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC)


def test_normalize_quote_rejects_missing_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        normalize_quote(
            {"price": 1},
            exchange="SSE",
            trade_date="2026-09-20",
            collected_at=datetime(2026, 9, 20, tzinfo=UTC),
        )


def test_deduplication_keys_are_deterministic_and_dataset_specific() -> None:
    timestamp = datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC)

    assert quote_key("SSE", "600519", timestamp, "sha256:abc") == quote_key(
        "SSE",
        "600519",
        timestamp,
        "sha256:abc",
    )
    assert bar_key("SSE", "600519", "1m", "none", timestamp) != transaction_key(
        "SSE",
        "600519",
        timestamp,
        price=Decimal("1468.20"),
        quantity=Decimal("100"),
        side="buy",
        source_offset=0,
    )
