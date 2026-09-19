from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from instrument_market.collectors.sharding import build_quote_shards
from instrument_market.pipeline.quality import QuoteQuality, evaluate_quote
from instrument_market.providers.models import PriceLevel, QuoteRecord


def quote(
    *,
    source_time: datetime,
    last_price: Decimal = Decimal("10.00"),
    bid: Decimal = Decimal("9.99"),
    ask: Decimal = Decimal("10.01"),
) -> QuoteRecord:
    return QuoteRecord(
        exchange="SSE",
        symbol="600000",
        source_time=source_time,
        collected_at=source_time + timedelta(milliseconds=300),
        last_price=last_price,
        previous_close=Decimal("9.90"),
        open_price=Decimal("9.95"),
        high_price=Decimal("10.10"),
        low_price=Decimal("9.80"),
        volume=Decimal("1000"),
        amount=Decimal("10000"),
        bids=(PriceLevel(price=bid, quantity=Decimal("100")),),
        asks=(PriceLevel(price=ask, quantity=Decimal("200")),),
    )


def test_build_quote_shards_is_deterministic_and_lossless() -> None:
    symbols = [f"{index:06d}" for index in range(101)]

    first = build_quote_shards(symbols, shard_count=8)
    second = build_quote_shards(reversed(symbols), shard_count=8)

    assert first == second
    assert sorted(symbol for shard in first for symbol in shard) == symbols
    assert max(map(len, first)) - min(map(len, first)) <= 1


def test_build_quote_shards_rejects_invalid_shard_count() -> None:
    with pytest.raises(ValueError, match="shard_count"):
        build_quote_shards(["600000"], shard_count=0)


def test_evaluate_quote_marks_fresh_valid_quote_healthy() -> None:
    now = datetime(2026, 9, 20, 1, 31, 3, tzinfo=UTC)

    result = evaluate_quote(quote(source_time=now - timedelta(seconds=1)), now=now)

    assert result.status is QuoteQuality.HEALTHY
    assert result.reasons == ()


def test_evaluate_quote_marks_old_quote_stale() -> None:
    now = datetime(2026, 9, 20, 1, 31, 10, tzinfo=UTC)

    result = evaluate_quote(
        quote(source_time=now - timedelta(seconds=4)),
        now=now,
        stale_after=timedelta(seconds=3),
    )

    assert result.status is QuoteQuality.STALE
    assert "source_time_exceeded" in result.reasons


@pytest.mark.parametrize(
    "candidate",
    [
        quote(
            source_time=datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC),
            last_price=Decimal("-1"),
        ),
        quote(
            source_time=datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC),
            bid=Decimal("10.02"),
            ask=Decimal("10.01"),
        ),
    ],
)
def test_evaluate_quote_rejects_invalid_market_values(candidate: QuoteRecord) -> None:
    result = evaluate_quote(
        candidate,
        now=datetime(2026, 9, 20, 1, 31, 3, tzinfo=UTC),
    )

    assert result.status is QuoteQuality.INVALID
    assert result.reasons
