from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from mootdx_collector.config import Settings
from mootdx_collector.provider import MARKETS, Provider
from mootdx_collector.spool import Spool
from mootdx_collector.universe import sync_universe

SHANGHAI = ZoneInfo("Asia/Shanghai")


def scoped_universe(universe: dict[str, Any] | None) -> dict[str, Any] | None:
    if not universe:
        return universe
    markets = {
        exchange: market
        for exchange, market in universe.get("markets", {}).items()
        if exchange in MARKETS
    }
    scoped = {
        **universe,
        "source": "mootdx",
        "scope": "sse_szse_candidate",
        "markets": markets,
        "instruments": [
            instrument
            for instrument in universe.get("instruments", [])
            if instrument.get("exchange") in MARKETS
        ],
    }
    scoped.pop("verification", None)
    scoped.pop("authority_error", None)
    return scoped


def active_session(now: datetime) -> bool:
    local = now.astimezone(SHANGHAI)
    minute = local.hour * 60 + local.minute
    # 周末与午间降频。尚无已核验节假日日历。假日可能多采但质量仍按源时间判定。
    return local.weekday() < 5 and (555 <= minute <= 690 or 780 <= minute <= 905)


def response_coverage(exchange: str, codes: list[str], rows: list[dict]) -> dict[str, Any]:
    expected, seen = set(codes), set()
    duplicates, unexpected = [], []
    for row in rows:
        code = row.get("code")
        if row.get("market") != MARKETS[exchange] or code not in expected:
            unexpected.append({"code": code, "market": row.get("market")})
        elif code in seen:
            duplicates.append(code)
        else:
            seen.add(code)
    return {
        "expected": len(expected),
        "received": len(seen),
        "missing": sorted(expected - seen),
        "duplicates": duplicates,
        "unexpected": unexpected,
    }


class Collector:
    def __init__(self, settings: Settings, spool: Spool, provider: Provider) -> None:
        self.settings, self.spool, self.provider = settings, spool, provider
        self.executor = ThreadPoolExecutor(max_workers=settings.workers)
        self.universe = scoped_universe(spool.get("universe"))

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.provider.close()

    def _fetch(self, exchange: str, codes: list[str]) -> dict[str, Any]:
        try:
            result = self.provider.quotes(exchange, codes)
        except Exception as error:
            result = {"rows": [], "source_id": "tdx-unavailable", "error": type(error).__name__}
        return {**result, "collected_at": datetime.now(UTC).isoformat()}

    def once(self) -> dict[str, Any]:
        cfg = self.settings
        if not self.spool.has_capacity(
            max_pending=cfg.max_pending,
            max_bytes=cfg.max_spool_bytes,
            min_free=cfg.min_free_bytes,
        ):
            result = {"status": "paused_capacity", "observed_at": datetime.now(UTC).isoformat()}
            self.spool.set("latest_round", result)
            return result
        now = datetime.now(UTC)
        if (
            not self.universe
            or not any(market["instruments"] for market in self.universe["markets"].values())
            or (now - datetime.fromisoformat(self.universe["observed_at"])).total_seconds()
            >= cfg.universe_refresh_seconds
        ):
            self.universe = sync_universe(self.provider, self.spool)
        round_id, started = str(uuid4()), time.monotonic()
        self.spool.set("active_round", {"round_id": round_id, "started_at": now.isoformat()})
        dates = {}
        for exchange, market in self.universe["markets"].items():
            instruments = market["instruments"]
            try:
                dates[exchange] = (
                    self.provider.trade_date(exchange, instruments[0]["code"])
                    if instruments
                    else None
                )
            except Exception:
                dates[exchange] = None
        futures = {}
        markets = {}
        for exchange, market in self.universe["markets"].items():
            instruments = market["instruments"]
            markets[exchange] = {
                "expected": len(instruments),
                "received": 0,
                "missing": [],
                "unexpected": [],
                "duplicates": [],
                "source_error": market.get("reason"),
                "universe_complete": market["complete"],
                "cached": market.get("cached", False),
            }
            for offset in range(0, len(instruments), cfg.batch_size):
                shard = instruments[offset : offset + cfg.batch_size]
                future = self.executor.submit(
                    self._fetch,
                    exchange,
                    [row["code"] for row in shard],
                )
                futures[future] = (exchange, shard)
        batch_ids = []
        for future in as_completed(futures):
            exchange, shard = futures[future]
            result = future.result()
            codes = [row["code"] for row in shard]
            coverage = response_coverage(exchange, codes, result["rows"])
            current = markets[exchange]
            current["received"] += coverage["received"]
            for key in ("missing", "unexpected", "duplicates"):
                current[key].extend(coverage[key])
            if result["error"]:
                current["source_error"] = result["error"]
            batch = {
                "batch_id": str(uuid4()),
                "exchange": exchange,
                "trade_date": dates[exchange],
                "source_id": result["source_id"],
                "collected_at": result["collected_at"],
                "quotes": result["rows"],
                "metadata": {
                    "round_id": round_id,
                    "requested": codes,
                    "trade_date_basis": "daily_bar_inferred" if dates[exchange] else "unknown",
                    "universe_source": self.universe["source"],
                    "instruments": {
                        row["code"]: {
                            "volunit": row.get("volunit"),
                            "decimal_point": row.get("decimal_point"),
                        }
                        for row in shard
                    },
                    "source_error": result["error"],
                },
            }
            # 所有已返回批次先持久化。阈值阻止下一轮。当前在途响应不丢弃。
            self.spool.put(
                "/internal/v1/market/quotes" if result["rows"] else "",
                batch,
            )
            batch_ids.append(batch["batch_id"])
        report = {
            "round_id": round_id,
            "observed_at": datetime.now(UTC).isoformat(),
            "status": "partial"
            if any(row["missing"] or not row["universe_complete"] for row in markets.values())
            else "collected",
            "universe_source": self.universe["source"],
            "expected": sum(row["expected"] for row in markets.values()),
            "received": sum(row["received"] for row in markets.values()),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "markets": markets,
            "batch_ids": batch_ids,
            "source_dates": dates,
            "node_switches": self.provider.switches,
            "delivery_totals_at_report": self.spool.stats()["delivered_quotes"],
        }
        self.spool.put(
            "/internal/v1/market/reports",
            {
                "batch_id": round_id,
                "kind": "coverage",
                "observed_at": report["observed_at"],
                "body": report,
            },
            checkpoint=("latest_round", report),
        )
        self.spool.set("active_round", None)
        return report
