from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from instrument_market.providers.models import PriceLevel, QuoteRecord

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _decimal(payload: dict[str, Any], *names: str, default: str = "0") -> Decimal:
    value: object = default
    for name in names:
        if name in payload and payload[name] is not None:
            value = payload[name]
            break
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"invalid decimal value for {names[0]}") from error


def _source_time(
    *,
    trade_date: str,
    server_time: object,
    fallback: datetime,
) -> datetime:
    if server_time in (None, ""):
        return fallback.astimezone(UTC)
    parsed_date = date.fromisoformat(trade_date)
    raw = str(server_time).strip()
    parsed_time = datetime.strptime(raw, "%H:%M:%S").time()
    localized = datetime.combine(parsed_date, parsed_time, tzinfo=SHANGHAI)
    return localized.astimezone(UTC)


def _levels(payload: dict[str, Any], side: str) -> tuple[PriceLevel, ...]:
    levels: list[PriceLevel] = []
    for level in range(1, 6):
        price = _decimal(payload, f"{side}{level}", default="0")
        quantity = _decimal(
            payload,
            f"{side}_vol{level}",
            f"{side}_volume{level}",
            default="0",
        )
        if price > 0 or quantity > 0:
            levels.append(PriceLevel(price=price, quantity=quantity))
    return tuple(levels)


def normalize_quote(
    payload: dict[str, Any],
    *,
    exchange: str,
    trade_date: str,
    collected_at: datetime,
    source_id: str = "",
    payload_hash: str = "",
) -> QuoteRecord:
    if collected_at.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    symbol = str(payload.get("code") or payload.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("symbol is required")

    return QuoteRecord(
        exchange=exchange,
        symbol=symbol,
        source_time=_source_time(
            trade_date=trade_date,
            server_time=payload.get("servertime"),
            fallback=collected_at,
        ),
        collected_at=collected_at.astimezone(UTC),
        last_price=_decimal(payload, "price", "last_price"),
        previous_close=_decimal(payload, "last_close", "previous_close"),
        open_price=_decimal(payload, "open", "open_price"),
        high_price=_decimal(payload, "high", "high_price"),
        low_price=_decimal(payload, "low", "low_price"),
        volume=_decimal(payload, "vol", "volume"),
        amount=_decimal(payload, "amount"),
        bids=_levels(payload, "bid"),
        asks=_levels(payload, "ask"),
        source_id=source_id,
        payload_hash=payload_hash,
    )
