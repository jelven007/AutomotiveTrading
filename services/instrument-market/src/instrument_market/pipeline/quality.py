from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from instrument_market.providers.models import QuoteRecord


class QuoteQuality(StrEnum):
    HEALTHY = "healthy"
    STALE = "stale"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class QualityResult:
    status: QuoteQuality
    reasons: tuple[str, ...]


def evaluate_quote(
    quote: QuoteRecord,
    *,
    now: datetime,
    stale_after: timedelta = timedelta(seconds=3),
) -> QualityResult:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    invalid_reasons: list[str] = []
    if quote.last_price < 0:
        invalid_reasons.append("negative_last_price")
    if quote.volume < 0 or quote.amount < 0:
        invalid_reasons.append("negative_volume_or_amount")
    if quote.bids and quote.asks and quote.bids[0].price > quote.asks[0].price:
        invalid_reasons.append("crossed_order_book")
    if quote.high_price > 0 and quote.low_price > 0 and quote.high_price < quote.low_price:
        invalid_reasons.append("invalid_high_low")
    if invalid_reasons:
        return QualityResult(QuoteQuality.INVALID, tuple(invalid_reasons))

    if now - quote.source_time > stale_after:
        return QualityResult(QuoteQuality.STALE, ("source_time_exceeded",))

    return QualityResult(QuoteQuality.HEALTHY, ())
