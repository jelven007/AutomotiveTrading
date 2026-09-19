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


def test_normalize_quote_accepts_millisecond_source_time() -> None:
    quote = normalize_quote(
        {"code": "600000", "price": 10, "servertime": "15:29:52.986"},
        exchange="SSE",
        trade_date="2026-09-18",
        collected_at=datetime(2026, 9, 20, tzinfo=UTC),
    )
    assert quote.source_time == datetime(2026, 9, 18, 7, 29, 52, 986000, tzinfo=UTC)


def test_normalize_quote_missing_time_is_not_healthy() -> None:
    from instrument_market.pipeline.quality import evaluate_quote

    now = datetime(2026, 9, 20, tzinfo=UTC)
    quote = normalize_quote(
        {"code": "600000", "price": 10},
        exchange="SSE",
        trade_date="2026-09-18",
        collected_at=now,
    )
    assert evaluate_quote(quote, now=now).status != "healthy"


def test_normalize_quote_converts_lots_and_rounds_source_float() -> None:
    quote = normalize_quote(
        {
            "code": "600000",
            "price": 11.700000000000001,
            "vol": 123,
            "bid1": 11.69,
            "bid_vol1": 4,
            "servertime": "15:00:00.001",
        },
        exchange="SSE",
        trade_date="2026-09-18",
        collected_at=datetime(2026, 9, 18, 7, 0, 1, tzinfo=UTC),
        metadata={
            "trade_date_basis": "verified",
            "instruments": {"600000": {"volunit": 100, "decimal_point": 2}},
        },
    )
    assert quote.last_price == Decimal("11.70")
    assert quote.volume == Decimal("12300")
    assert quote.bids[0].quantity == Decimal("400")
    assert quote.quality_reasons == ()


@pytest.mark.parametrize(
    "server_time,basis,unit,expected",
    [
        ("15:00:00", "daily_bar_inferred", 100, "partial"),
        ("15:00:00", "verified", None, "partial"),
        ("0", "verified", 100, "unavailable"),
        ("bad", "verified", 100, "unavailable"),
        ("15:10:00", "verified", 100, "invalid"),
    ],
)
def test_normalize_quote_unknown_and_future_fields_are_not_healthy(
    server_time, basis, unit, expected
):
    from instrument_market.pipeline.quality import evaluate_quote

    now = datetime(2026, 9, 18, 7, 0, 1, tzinfo=UTC)
    quote = normalize_quote(
        {"code": "600000", "price": 10, "servertime": server_time},
        exchange="SSE",
        trade_date="2026-09-18",
        collected_at=now,
        metadata={"trade_date_basis": basis, "instruments": {"600000": {"volunit": unit}}},
    )
    assert evaluate_quote(quote, now=now).status == expected


@pytest.mark.parametrize("price", ["NaN", "Infinity", "not-a-price"])
def test_normalize_quote_rejects_nonfinite_or_malformed_price(price):
    with pytest.raises(ValueError, match="decimal"):
        normalize_quote(
            {"code": "600000", "price": price},
            exchange="SSE",
            trade_date=None,
            collected_at=datetime.now(UTC),
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
