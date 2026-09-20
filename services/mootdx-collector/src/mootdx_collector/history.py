from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock_time
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from mootdx_collector.config import Settings
from mootdx_collector.provider import MARKETS, Provider
from mootdx_collector.spool import Spool

SHANGHAI = ZoneInfo("Asia/Shanghai")


def minute_datetimes(trade_date: str, count: int) -> list[datetime]:
    """TDX 分时没有时间字段, 按沪深 240 个连续竞价分钟补齐."""
    if not 0 <= count <= 240:
        raise ValueError("minute count must be within 0..240")
    local_date = date.fromisoformat(trade_date)
    morning = datetime.combine(local_date, clock_time(9, 31), tzinfo=SHANGHAI)
    afternoon = datetime.combine(local_date, clock_time(13, 1), tzinfo=SHANGHAI)
    return [
        ((morning + timedelta(minutes=index)) if index < 120 else (
            afternoon + timedelta(minutes=index - 120)
        )).astimezone(UTC)
        for index in range(count)
    ]


class HistoryCollector:
    """按持久化证券游标渐进采集, 不参与实时快照线程池."""

    def __init__(
        self,
        settings: Settings,
        spool: Spool,
        provider: Provider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.spool = spool
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(UTC))
        self._last_request_at = 0.0

    def close(self) -> None:
        self.provider.close()

    def collect_one(self) -> dict[str, Any]:
        now = self.clock()
        if not self.spool.has_capacity(
            max_pending=self.settings.max_pending,
            max_bytes=self.settings.max_spool_bytes,
            min_free=self.settings.min_free_bytes,
        ):
            return self._state("paused_capacity", now)

        universe = self.spool.get("universe") or {}
        instruments = sorted(
            (
                row
                for row in universe.get("instruments", [])
                if row.get("exchange") in MARKETS
            ),
            key=lambda row: (row["exchange"], row["code"]),
        )
        if not instruments:
            return self._state("waiting_universe", now)

        source_dates = (self.spool.get("latest_round") or {}).get("source_dates", {})
        cursor = self.spool.get("history_cursor") or {}
        if cursor.get("source_dates") != source_dates:
            cursor = {"index": 0, "source_dates": source_dates}
        if cursor.get("completed_dates") == source_dates:
            return self._state("caught_up", now, source_dates=source_dates)

        index = int(cursor.get("index", 0)) % len(instruments)
        instrument = instruments[index]
        exchange, symbol = instrument["exchange"], instrument["code"]
        trade_date = source_dates.get(exchange)
        if not trade_date:
            return self._state(
                "waiting_trade_date",
                now,
                exchange=exchange,
                symbol=symbol,
            )

        collected_at = now.astimezone(UTC).isoformat()
        batches: list[str] = []
        datasets: dict[str, Any] = {}
        self._collect_bars(
            exchange,
            symbol,
            trade_date,
            collected_at,
            instrument,
            batches,
            datasets,
        )
        self._collect_minutes(
            exchange,
            symbol,
            trade_date,
            collected_at,
            instrument,
            batches,
            datasets,
        )
        self._collect_transactions(
            exchange,
            symbol,
            trade_date,
            collected_at,
            instrument,
            batches,
            datasets,
        )

        status = "collected" if all(item["complete"] for item in datasets.values()) else "partial"
        next_index = index + 1
        next_cursor: dict[str, Any] = {
            "index": next_index % len(instruments),
            "source_dates": source_dates,
        }
        if next_index >= len(instruments):
            next_cursor["completed_dates"] = source_dates
        report = {
            "status": status,
            "observed_at": self.clock().astimezone(UTC).isoformat(),
            "exchange": exchange,
            "symbol": symbol,
            "trade_date": trade_date,
            "datasets": datasets,
            "batch_ids": batches,
            "cursor": next_cursor,
        }
        report_id = str(uuid4())
        self.spool.put(
            "/internal/v1/market/reports",
            {
                "batch_id": report_id,
                "kind": "history_coverage",
                "observed_at": report["observed_at"],
                "body": report,
            },
            checkpoints={"history_cursor": next_cursor, "latest_history": report},
        )
        return report

    def _collect_bars(
        self,
        exchange: str,
        symbol: str,
        trade_date: str,
        collected_at: str,
        instrument: dict[str, Any],
        batches: list[str],
        datasets: dict[str, Any],
    ) -> None:
        try:
            result = self._request(
                self.provider.daily_bars,
                exchange,
                symbol,
                self.settings.history_bar_count,
            )
            rows = [dict(row) for row in result["rows"]]
            complete, reason = bool(rows), None if rows else "empty_response"
            if rows:
                batches.append(
                    self._put(
                        "bars",
                        exchange,
                        symbol,
                        trade_date,
                        collected_at,
                        result["source_id"],
                        rows,
                        {
                            "interval": "1d",
                            "adjustment": "none",
                            "requested": self.settings.history_bar_count,
                            "complete": complete,
                            "volunit": instrument.get("volunit"),
                        },
                    )
                )
        except Exception as error:
            rows, complete, reason = [], False, type(error).__name__
        datasets["bar"] = {
            "received": len(rows),
            "complete": complete,
            "reason": reason,
        }

    def _collect_minutes(
        self,
        exchange: str,
        symbol: str,
        trade_date: str,
        collected_at: str,
        instrument: dict[str, Any],
        batches: list[str],
        datasets: dict[str, Any],
    ) -> None:
        try:
            result = self._request(
                self.provider.minute_history,
                exchange,
                symbol,
                trade_date,
            )
            rows = [dict(row) for row in result["rows"][:240]]
            timestamps = minute_datetimes(trade_date, len(rows))
            for index, row in enumerate(rows):
                row.update(source_offset=index, datetime=timestamps[index].isoformat())
            complete = len(rows) == 240
            reason = None if complete else "minute_count_mismatch"
            if rows:
                batches.append(
                    self._put(
                        "minutes",
                        exchange,
                        symbol,
                        trade_date,
                        collected_at,
                        result["source_id"],
                        rows,
                        {
                            "expected": 240,
                            "complete": complete,
                            "volunit": instrument.get("volunit"),
                        },
                    )
                )
        except Exception as error:
            rows, complete, reason = [], False, type(error).__name__
        datasets["minute"] = {
            "received": len(rows),
            "complete": complete,
            "reason": reason,
        }

    def _collect_transactions(
        self,
        exchange: str,
        symbol: str,
        trade_date: str,
        collected_at: str,
        instrument: dict[str, Any],
        batches: list[str],
        datasets: dict[str, Any],
    ) -> None:
        page_size = self.settings.history_transaction_page_size
        rows: list[dict[str, Any]] = []
        source_ids: list[str] = []
        pages = 0
        complete, reason = False, None
        try:
            for page in range(self.settings.history_transaction_max_pages):
                start = page * page_size
                result = self._request(
                    self.provider.transaction_page,
                    exchange,
                    symbol,
                    trade_date,
                    start,
                    page_size,
                )
                page_rows = [dict(row) for row in result["rows"]]
                source_ids.append(result["source_id"])
                pages += 1
                for offset, row in enumerate(page_rows):
                    row["source_offset"] = start + offset
                rows.extend(page_rows)
                if len(page_rows) < page_size:
                    complete = True
                    break
            if not complete:
                reason = "page_limit_reached"
            if rows:
                batches.append(
                    self._put(
                        "transactions",
                        exchange,
                        symbol,
                        trade_date,
                        collected_at,
                        source_ids[-1],
                        rows,
                        {
                            "page_size": page_size,
                            "pages": pages,
                            "complete": complete,
                            "reason": reason,
                            "source_ids": list(dict.fromkeys(source_ids)),
                            "volunit": instrument.get("volunit"),
                        },
                    )
                )
        except Exception as error:
            complete, reason = False, type(error).__name__
        datasets["transaction"] = {
            "received": len(rows),
            "pages": pages,
            "complete": complete,
            "reason": reason,
        }

    def _put(
        self,
        dataset: str,
        exchange: str,
        symbol: str,
        trade_date: str,
        collected_at: str,
        source_id: str,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> str:
        batch_id = str(uuid4())
        self.spool.put(
            f"/internal/v1/market/{dataset}",
            {
                "batch_id": batch_id,
                "exchange": exchange,
                "symbol": symbol,
                "trade_date": trade_date,
                "source_id": source_id,
                "collected_at": collected_at,
                "rows": rows,
                "metadata": metadata,
            },
        )
        return batch_id

    def _request(self, operation: Callable[..., Any], *args: Any) -> Any:
        interval = self.settings.history_request_interval
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        result = operation(*args)
        self._last_request_at = time.monotonic()
        return result

    def _state(self, status: str, now: datetime, **details: Any) -> dict[str, Any]:
        state = {
            "status": status,
            "observed_at": now.astimezone(UTC).isoformat(),
            **details,
        }
        self.spool.set("latest_history", state)
        return state
