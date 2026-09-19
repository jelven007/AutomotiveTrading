from __future__ import annotations

from datetime import UTC, date, datetime, time
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
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) >= Decimal("1e24"):
            raise ValueError("decimal out of range")
        return result
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"invalid decimal value for {names[0]}") from error


def _source_time(
    *,
    trade_date: str | None,
    server_time: object,
    fallback: datetime,
) -> datetime:
    if not trade_date or server_time in (None, "", "0", 0):
        raise ValueError("source time unknown")
    parsed_date = date.fromisoformat(trade_date)
    raw = str(server_time).strip()
    parsed_time = time.fromisoformat(raw)
    if parsed_time.tzinfo is not None or len(raw) < 8:
        raise ValueError("invalid server time")
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
    trade_date: str | None,
    collected_at: datetime,
    source_id: str = "",
    payload_hash: str = "",
    metadata: dict[str, Any] | None = None,
) -> QuoteRecord:
    if collected_at.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    symbol = str(payload.get("code") or payload.get("symbol") or "").strip()
    if not symbol.isascii() or not symbol.isdigit() or len(symbol) != 6:
        raise ValueError("symbol is required")
    metadata = metadata or {}
    reasons: list[str] = []
    try:
        source_time = _source_time(
            trade_date=trade_date,
            server_time=payload.get("servertime"),
            fallback=collected_at,
        )
    except (ValueError, TypeError):
        # 未知时间使用明确哨兵并降级。绝不把采集时刻冒充上游时刻。
        source_time = datetime(1970, 1, 1, tzinfo=UTC)
        reasons.append("source_time_unknown")
    if metadata.get("trade_date_basis") != "verified":
        reasons.append("trade_date_unverified")
    instrument = metadata.get("instruments", {}).get(symbol, {})
    unit = instrument.get("volunit")
    if unit is None or not isinstance(unit, int) or not 0 < unit <= 10000:
        unit = 1
        reasons.append("volume_unit_unknown")
    precision = instrument.get("decimal_point")

    def price(*names: str) -> Decimal:
        value = _decimal(payload, *names)
        if abs(value) >= Decimal("1e14"):
            raise ValueError("price out of range")
        if isinstance(precision, int) and 0 <= precision <= 6:
            value = value.quantize(Decimal(10) ** -precision)
        return value

    def levels(side: str) -> tuple[PriceLevel, ...]:
        return tuple(
            PriceLevel(
                price=level.price.quantize(Decimal(10) ** -precision)
                if isinstance(precision, int) and 0 <= precision <= 6
                else level.price,
                quantity=level.quantity * unit,
            )
            for level in _levels(payload, side)
        )

    return QuoteRecord(
        exchange=exchange,
        symbol=symbol,
        source_time=source_time,
        collected_at=collected_at.astimezone(UTC),
        last_price=price("price", "last_price"),
        previous_close=price("last_close", "previous_close"),
        open_price=price("open", "open_price"),
        high_price=price("high", "high_price"),
        low_price=price("low", "low_price"),
        volume=_decimal(payload, "vol", "volume") * unit,
        amount=_decimal(payload, "amount"),
        bids=levels("bid"),
        asks=levels("ask"),
        source_id=source_id,
        payload_hash=payload_hash,
        quality_reasons=tuple(reasons),
    )
