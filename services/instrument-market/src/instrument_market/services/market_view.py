from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol


class QueryClient(Protocol):
    def query_json_each_row(
        self,
        query: str,
        *,
        parameters: dict[str, str | int] | None = None,
    ) -> list[dict[str, Any]]: ...


LATEST_QUOTES_QUERY = """
WITH
universe AS (
    SELECT
        JSONExtractString(item, 'exchange') AS exchange,
        JSONExtractString(item, 'code') AS symbol,
        JSONExtractString(item, 'name') AS name
    FROM (
        SELECT arrayJoin(
            JSONExtractArrayRaw(argMax(body, observed_at), 'instruments')
        ) AS item
        FROM collector_report
        WHERE kind = 'universe'
    )
),
latest AS (
    SELECT
        exchange,
        symbol,
        argMax(source_time, collected_at) AS source_time,
        max(collected_at) AS latest_collected_at,
        argMax(last_price, collected_at) AS last_price,
        argMax(previous_close, collected_at) AS previous_close,
        argMax(open_price, collected_at) AS open_price,
        argMax(high_price, collected_at) AS high_price,
        argMax(low_price, collected_at) AS low_price,
        argMax(volume, collected_at) AS volume,
        argMax(amount, collected_at) AS amount,
        argMax(quality_status, collected_at) AS quality_status,
        argMax(quality_reasons, collected_at) AS quality_reasons,
        argMax(source_id, collected_at) AS source_id
    FROM market_quote
    WHERE exchange IN ('SSE', 'SZSE')
    GROUP BY exchange, symbol
)
SELECT
    latest.exchange,
    latest.symbol,
    universe.name,
    source_time,
    latest_collected_at AS collected_at,
    last_price,
    previous_close,
    open_price,
    high_price,
    low_price,
    volume,
    amount,
    quality_status,
    quality_reasons,
    source_id,
    count() OVER () AS available
FROM latest
LEFT JOIN universe USING (exchange, symbol)
ORDER BY exchange, symbol
LIMIT {limit:UInt32}
"""

COVERAGE_QUERY = """
SELECT body
FROM collector_report FINAL
WHERE kind = 'coverage'
ORDER BY observed_at DESC
LIMIT 1
"""


class MarketViewService:
    def __init__(self, client: QueryClient) -> None:
        self.client = client

    def latest_quotes(self, *, limit: int) -> dict[str, Any]:
        rows = self.client.query_json_each_row(
            LATEST_QUOTES_QUERY,
            parameters={"limit": limit},
        )
        report_rows = self.client.query_json_each_row(COVERAGE_QUERY)
        items = [self._quote(row) for row in rows]
        quality = Counter(item["quality_status"] for item in items)
        return {
            "scope": ["SSE", "SZSE"],
            "as_of": max((item["collected_at"] for item in items), default=None),
            "available": int(rows[0].get("available", len(items))) if rows else 0,
            "returned": len(items),
            "quality": dict(sorted(quality.items())),
            "coverage": self._coverage(report_rows),
            "items": items,
        }

    @staticmethod
    def _quote(row: dict[str, Any]) -> dict[str, Any]:
        last_price = Decimal(str(row.get("last_price", 0)))
        previous_close = Decimal(str(row.get("previous_close", 0)))
        change_percent = (
            (last_price - previous_close) / previous_close * 100
            if previous_close > 0
            else Decimal(0)
        )
        return {
            "exchange": row["exchange"],
            "symbol": row["symbol"],
            "name": str(row.get("name") or "").replace("\x00", "").strip(),
            "source_time": _utc(row.get("source_time")),
            "collected_at": _utc(row.get("collected_at")),
            "last_price": str(last_price),
            "previous_close": str(previous_close),
            "change_percent": str(change_percent.quantize(Decimal("0.01"))),
            "open_price": str(row.get("open_price", 0)),
            "high_price": str(row.get("high_price", 0)),
            "low_price": str(row.get("low_price", 0)),
            "volume": str(row.get("volume", 0)),
            "amount": str(row.get("amount", 0)),
            "quality_status": str(row.get("quality_status") or "unavailable"),
            "quality_reasons": _json_list(row.get("quality_reasons")),
            "source_id": str(row.get("source_id") or ""),
        }

    @staticmethod
    def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rows:
            return None
        raw = rows[0].get("body")
        report = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(report, dict):
            return None
        markets = report.get("markets", {})
        selected = {exchange: markets.get(exchange, {}) for exchange in ("SSE", "SZSE")}
        expected = sum(int(market.get("expected", 0)) for market in selected.values())
        received = sum(int(market.get("received", 0)) for market in selected.values())
        missing = sum(len(market.get("missing", [])) for market in selected.values())
        complete = all(
            market.get("universe_complete") is True
            and not market.get("source_error")
            and not market.get("missing")
            for market in selected.values()
        )
        return {
            "status": "collected" if complete and expected == received else "partial",
            "expected": expected,
            "received": received,
            "missing": missing,
            "duration_ms": int(report.get("duration_ms", 0)),
            "observed_at": report.get("observed_at"),
            "source": report.get("universe_source", "mootdx"),
            "markets": selected,
        }


def _utc(value: object) -> str | None:
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []
