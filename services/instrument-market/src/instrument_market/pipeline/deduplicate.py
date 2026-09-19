from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal


def _digest(dataset: str, *parts: object) -> str:
    normalized = "|".join([dataset, *(str(part) for part in parts)])
    return f"{dataset}:sha256:{hashlib.sha256(normalized.encode()).hexdigest()}"


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("deduplication timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def quote_key(
    exchange: str,
    symbol: str,
    source_time: datetime,
    payload_hash: str,
) -> str:
    return _digest("quote", exchange, symbol, _utc_text(source_time), payload_hash)


def bar_key(
    exchange: str,
    symbol: str,
    interval: str,
    adjustment: str,
    event_time: datetime,
) -> str:
    return _digest(
        "bar",
        exchange,
        symbol,
        interval,
        adjustment,
        _utc_text(event_time),
    )


def transaction_key(
    exchange: str,
    symbol: str,
    event_time: datetime,
    *,
    price: Decimal,
    quantity: Decimal,
    side: str,
    source_offset: int,
) -> str:
    return _digest(
        "transaction",
        exchange,
        symbol,
        _utc_text(event_time),
        price,
        quantity,
        side,
        source_offset,
    )
