from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from instrument_market.pipeline.envelope import RawEnvelope
from instrument_market.providers.models import Dataset, ProviderName
from instrument_market.storage.clickhouse import raw_history_row
from instrument_market.storage.receipts import ReceiptStore

SHANGHAI = ZoneInfo("Asia/Shanghai")
HISTORY_DATASETS = frozenset({Dataset.BAR, Dataset.MINUTE, Dataset.TRANSACTION})
SIDE_NAMES = {0: "buy", 1: "sell", 2: "neutral"}


class HistorySink(Protocol):
    def insert_json_each_row(
        self,
        table: str,
        rows: list[dict[str, Any]],
    ) -> None: ...


class HistoryQueryClient(Protocol):
    def query_json_each_row(
        self,
        query: str,
        *,
        parameters: Mapping[str, str | int] | None = None,
    ) -> list[dict[str, Any]]: ...


class HistoryIngestionService:
    def __init__(
        self,
        sink: HistorySink,
        *,
        receipts: ReceiptStore | None = None,
    ) -> None:
        self.sink = sink
        self.receipts = receipts or ReceiptStore()

    def ingest(
        self,
        *,
        dataset: str,
        batch_id: str,
        exchange: str,
        symbol: str,
        trade_date: str,
        source_id: str,
        collected_at: datetime,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            parsed_dataset = Dataset(dataset)
        except ValueError as error:
            raise ValueError("unsupported history dataset") from error
        if parsed_dataset not in HISTORY_DATASETS:
            raise ValueError("unsupported history dataset")
        body = {
            "dataset": dataset,
            "exchange": exchange,
            "symbol": symbol,
            "trade_date": trade_date,
            "source_id": source_id,
            "collected_at": collected_at.isoformat(),
            "rows": rows,
            "metadata": metadata or {},
        }
        return self.receipts.apply(
            batch_id,
            body,
            lambda: self._persist(
                parsed_dataset,
                batch_id,
                exchange,
                symbol,
                trade_date,
                source_id,
                collected_at,
                rows,
                metadata or {},
            ),
        )

    def _persist(
        self,
        dataset: Dataset,
        batch_id: str,
        exchange: str,
        symbol: str,
        trade_date: str,
        source_id: str,
        collected_at: datetime,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if exchange not in {"SSE", "SZSE"}:
            raise ValueError("unsupported exchange")
        if len(symbol) != 6 or not symbol.isascii() or not symbol.isdigit():
            raise ValueError("invalid symbol")
        if collected_at.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")
        date.fromisoformat(trade_date)

        raw_rows = []
        envelopes: list[RawEnvelope] = []
        for index, payload in enumerate(rows):
            source_time = self._source_time(dataset, trade_date, payload)
            envelope = RawEnvelope.create(
                provider=ProviderName.MOOTDX,
                dataset=dataset,
                market="CN",
                exchange=exchange,
                symbol=symbol,
                source_time=source_time,
                collected_at=collected_at,
                source_id=source_id,
                request={"batch_id": batch_id, "row_index": index},
                payload=payload,
            )
            envelope = replace(
                envelope,
                event_id=str(uuid5(NAMESPACE_URL, f"{batch_id}/{index}")),
            )
            envelopes.append(envelope)
            raw_rows.append(
                raw_history_row(
                    envelope,
                    batch_id=batch_id,
                    row_index=index,
                    metadata=metadata,
                )
            )
        self.sink.insert_json_each_row("market_history_raw", raw_rows)

        coverage = "healthy" if metadata.get("complete") is True else "partial"
        standard_rows, errors = [], []
        for index, (payload, envelope) in enumerate(zip(rows, envelopes, strict=True)):
            try:
                normalized = self._normalize(
                    dataset,
                    batch_id,
                    exchange,
                    symbol,
                    trade_date,
                    source_id,
                    payload,
                    envelope,
                    metadata,
                    coverage,
                )
            except (ValueError, TypeError, ArithmeticError) as error:
                errors.append({"row_index": index, "reason": str(error)})
                continue
            standard_rows.append(normalized)
        if errors:
            coverage = "partial"
            for row in standard_rows:
                row["quality_status"] = coverage
        self.sink.insert_json_each_row(self._table(dataset), standard_rows)
        return {
            "batch_id": batch_id,
            "received": len(rows),
            "accepted": len(standard_rows),
            "rejected": len(errors),
            "errors": errors,
            "coverage": coverage,
        }

    def _normalize(
        self,
        dataset: Dataset,
        batch_id: str,
        exchange: str,
        symbol: str,
        trade_date: str,
        source_id: str,
        payload: dict[str, Any],
        envelope: RawEnvelope,
        metadata: dict[str, Any],
        coverage: str,
    ) -> dict[str, Any]:
        common = {
            "exchange": exchange,
            "symbol": symbol,
            "provider": ProviderName.MOOTDX.value,
            "source_id": source_id,
            "payload_hash": envelope.payload_hash,
            "batch_id": batch_id,
            "quality_status": coverage,
            "metadata_json": _json(metadata),
        }
        unit = _volume_unit(metadata)
        if dataset is Dataset.BAR:
            return {
                **common,
                "interval": str(metadata.get("interval") or "1d"),
                "adjustment": str(metadata.get("adjustment") or "none"),
                "event_time": _local_datetime(payload.get("datetime")),
                "open": _decimal(payload, "open", positive=True),
                "high": _decimal(payload, "high", positive=True),
                "low": _decimal(payload, "low", positive=True),
                "close": _decimal(payload, "close", positive=True),
                "volume": _decimal(payload, "vol") * unit,
                "amount": _decimal(payload, "amount"),
            }
        if dataset is Dataset.MINUTE:
            return {
                **common,
                "trade_date": trade_date,
                "event_time": _aware_datetime(payload.get("datetime")),
                "price": _decimal(payload, "price", positive=True),
                "volume": _decimal(payload, "vol") * unit,
                "source_offset": _offset(payload),
            }
        raw_side = payload.get("buyorsell")
        if not isinstance(raw_side, int):
            raise ValueError("invalid transaction side")
        side_code = raw_side
        if side_code not in SIDE_NAMES:
            raise ValueError("invalid transaction side")
        event_time = _transaction_time(trade_date, payload.get("time"))
        return {
            **common,
            "trade_date": trade_date,
            "event_time": event_time,
            "price": _decimal(payload, "price", positive=True),
            "quantity": _decimal(payload, "vol") * unit,
            "side": SIDE_NAMES[side_code],
            "source_offset": _offset(payload),
        }

    @staticmethod
    def _source_time(dataset: Dataset, trade_date: str, payload: dict[str, Any]) -> datetime:
        try:
            if dataset is Dataset.BAR:
                return _local_datetime(payload.get("datetime"))
            if dataset is Dataset.MINUTE:
                return _aware_datetime(payload.get("datetime"))
            return _transaction_time(trade_date, payload.get("time"))
        except (ValueError, TypeError):
            return datetime(1970, 1, 1, tzinfo=UTC)

    @staticmethod
    def _table(dataset: Dataset) -> str:
        return {
            Dataset.BAR: "market_bar",
            Dataset.MINUTE: "market_minute",
            Dataset.TRANSACTION: "market_transaction",
        }[dataset]


class HistoryViewService:
    def __init__(self, client: HistoryQueryClient) -> None:
        self.client = client

    def bars(self, *, exchange: str, symbol: str, interval: str, limit: int) -> dict[str, Any]:
        rows = self.client.query_json_each_row(
            """
            SELECT event_time, open, high, low, close, volume, amount,
                   source_id, quality_status
            FROM market_bar FINAL
            WHERE exchange={exchange:String} AND symbol={symbol:String}
              AND interval={interval:String}
            ORDER BY event_time DESC
            LIMIT {limit:UInt32}
            """,
            parameters={
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        items = [
            {
                **_pick(row, "source_id", "quality_status"),
                "event_time": _utc(row["event_time"]),
                "open": str(row["open"]),
                "high": str(row["high"]),
                "low": str(row["low"]),
                "close": str(row["close"]),
                "volume": str(row["volume"]),
                "amount": str(row["amount"]),
            }
            for row in reversed(rows)
        ]
        return self._response(exchange, symbol, items)

    def minutes(
        self,
        *,
        exchange: str,
        symbol: str,
        trade_date: str | None,
    ) -> dict[str, Any]:
        rows = self.client.query_json_each_row(
            _dated_query(
                "market_minute",
                (
                    "trade_date, event_time, price, volume, source_offset, "
                    "source_id, quality_status"
                ),
                trade_date,
            ),
            parameters=_date_parameters(exchange, symbol, trade_date, limit=240),
        )
        items = [
            {
                **_pick(row, "source_id", "quality_status"),
                "event_time": _utc(row["event_time"]),
                "price": str(row["price"]),
                "volume": str(row["volume"]),
                "source_offset": int(row["source_offset"]),
            }
            for row in rows
        ]
        selected_date = trade_date or (
            str(rows[0]["trade_date"]) if rows and rows[0].get("trade_date") else None
        )
        return self._response(exchange, symbol, items, trade_date=selected_date)

    def transactions(
        self,
        *,
        exchange: str,
        symbol: str,
        trade_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        rows = self.client.query_json_each_row(
            _dated_query(
                "market_transaction",
                (
                    "trade_date, event_time, price, quantity, side, source_offset, "
                    "source_id, quality_status"
                ),
                trade_date,
                newest_first=True,
            ),
            parameters=_date_parameters(exchange, symbol, trade_date, limit=limit),
        )
        items = [
            {
                **_pick(row, "source_id", "quality_status"),
                "event_time": _utc(row["event_time"]),
                "price": str(row["price"]),
                "quantity": str(row["quantity"]),
                "side": str(row["side"]),
                "source_offset": int(row["source_offset"]),
            }
            for row in rows
        ]
        selected_date = trade_date or (
            str(rows[0]["trade_date"]) if rows and rows[0].get("trade_date") else None
        )
        return self._response(exchange, symbol, items, trade_date=selected_date)

    @staticmethod
    def _response(
        exchange: str,
        symbol: str,
        items: list[dict[str, Any]],
        *,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        coverage = (
            "pending"
            if not items
            else "partial"
            if any(item["quality_status"] != "healthy" for item in items)
            else "collected"
        )
        result: dict[str, Any] = {
            "provider": ProviderName.MOOTDX.value,
            "exchange": exchange,
            "symbol": symbol,
            "coverage": coverage,
            "items": items,
        }
        if trade_date is not None or not items:
            result["trade_date"] = trade_date
        return result


def _dated_query(
    table: str,
    fields: str,
    trade_date: str | None,
    *,
    newest_first: bool = False,
) -> str:
    date_filter = (
        "trade_date={trade_date:Date}"
        if trade_date
        else (
            f"trade_date=(SELECT max(trade_date) FROM {table} "
            "WHERE exchange={exchange:String} AND symbol={symbol:String})"
        )
    )
    order = "DESC" if newest_first else "ASC"
    return f"""
        SELECT {fields}
        FROM {table} FINAL
        WHERE exchange={{exchange:String}} AND symbol={{symbol:String}}
          AND {date_filter}
        ORDER BY event_time {order}, source_offset {order}
        LIMIT {{limit:UInt32}}
    """


def _date_parameters(
    exchange: str,
    symbol: str,
    trade_date: str | None,
    *,
    limit: int,
) -> dict[str, str | int]:
    parameters: dict[str, str | int] = {
        "exchange": exchange,
        "symbol": symbol,
        "limit": limit,
    }
    if trade_date:
        parameters["trade_date"] = trade_date
    return parameters


def _decimal(payload: dict[str, Any], name: str, *, positive: bool = False) -> Decimal:
    try:
        value = Decimal(str(payload[name]))
    except (KeyError, InvalidOperation) as error:
        raise ValueError(f"invalid decimal value for {name}") from error
    if not value.is_finite() or value < 0 or (positive and value <= 0):
        raise ValueError(f"invalid decimal value for {name}")
    return value


def _volume_unit(metadata: dict[str, Any]) -> Decimal:
    value = metadata.get("volunit")
    if not isinstance(value, int) or not 0 < value <= 10000:
        raise ValueError("invalid volume unit")
    return Decimal(value)


def _offset(payload: dict[str, Any]) -> int:
    value = payload.get("source_offset")
    if not isinstance(value, int) or not 0 <= value <= 65535:
        raise ValueError("invalid source offset")
    return value


def _local_datetime(value: object) -> datetime:
    parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M")
    return parsed.replace(tzinfo=SHANGHAI).astimezone(UTC)


def _aware_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return parsed.astimezone(UTC)


def _transaction_time(trade_date: str, value: object) -> datetime:
    parsed_time = time.fromisoformat(str(value))
    if parsed_time < time(9, 15) or parsed_time > time(15, 0):
        raise ValueError("transaction time outside market session")
    localized = datetime.combine(
        date.fromisoformat(trade_date),
        parsed_time,
        tzinfo=SHANGHAI,
    )
    return localized.astimezone(UTC)


def _pick(row: dict[str, Any], *names: str) -> dict[str, str]:
    return {name: str(row.get(name) or "") for name in names}


def _utc(value: object) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
