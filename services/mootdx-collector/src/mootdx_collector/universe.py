from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from mootdx_collector.provider import MARKETS, Provider
from mootdx_collector.spool import Spool


def is_candidate(exchange: str, code: str) -> bool:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    prefixes = {"SSE": ("60", "68"), "SZSE": ("00", "30")}.get(exchange)
    return prefixes is not None and code.startswith(prefixes)


def enumerate_market(provider: Provider, spool: Spool, exchange: str) -> dict[str, Any]:
    if exchange not in MARKETS:
        raise ValueError("unsupported_exchange")
    market = MARKETS[exchange]
    count, _ = provider.call("get_security_count", market)
    if not isinstance(count, int) or not 0 < count <= 200000:
        raise ValueError("invalid_security_count")
    offset, seen, instruments = 0, set(), []
    while offset < count:
        rows, source_id = provider.call("get_security_list", market, offset)
        spool.put(
            "",
            {
                "dataset": "instrument_page",
                "exchange": exchange,
                "offset": offset,
                "source_id": source_id,
                "rows": rows,
            },
        )
        if not rows:
            raise ValueError("empty_security_page")
        codes = [str(row["code"]) for row in rows]
        if seen.intersection(codes) or len(set(codes)) != len(codes):
            raise ValueError("repeated_security_page")
        seen.update(codes)
        for row in rows:
            if is_candidate(exchange, row["code"]):
                instruments.append(
                    {
                        "exchange": exchange,
                        "code": row["code"],
                        "name": row["name"],
                        "volunit": row.get("volunit"),
                        "decimal_point": row.get("decimal_point"),
                    }
                )
        offset += len(rows)
    current_count, _ = provider.call("get_security_count", market)
    complete = current_count == count == offset
    return {
        "instruments": instruments,
        "complete": complete,
        "protocol_count": count,
        "reason": None if complete else "security_count_changed",
    }


def authoritative_universe(token: str) -> list[dict[str, str]]:
    with httpx.Client(timeout=15, trust_env=False) as client:
        response = client.post(
            "https://api.tushare.pro",
            json={
                "api_name": "stock_basic",
                "token": token,
                "params": {"list_status": "L"},
                "fields": "ts_code,symbol,name,exchange,list_status",
            },
        )
        response.raise_for_status()
        body = response.json()
    if body.get("code") != 0 or not body.get("data", {}).get("items"):
        raise ValueError("tushare_universe_unavailable")
    data = body["data"]
    rows = [dict(zip(data["fields"], row, strict=True)) for row in data["items"]]
    mapping = {"SSE": "SSE", "SZSE": "SZSE"}
    return [
        {"code": row["symbol"], "name": row["name"], "exchange": mapping[row["exchange"]]}
        for row in rows
        if row["exchange"] in mapping and row["list_status"] == "L"
    ]


def sync_universe(provider: Provider, spool: Spool, token: str = "") -> dict[str, Any]:
    previous = spool.get("universe") or {}
    markets: dict[str, Any] = {}
    for exchange in MARKETS:
        try:
            result = enumerate_market(provider, spool, exchange)
        except Exception as error:
            result = {"instruments": [], "complete": False, "reason": type(error).__name__}
        if not result["complete"] and previous.get("markets", {}).get(exchange):
            result["instruments"] = previous["markets"][exchange]["instruments"]
            result["cached"] = True
            result["last_success_at"] = previous["markets"][exchange].get("last_success_at")
        elif result["complete"]:
            result["last_success_at"] = datetime.now(UTC).isoformat()
        markets[exchange] = result

    verification = "unverified"
    authority_error = "tushare_token_missing"
    if token:
        try:
            authority = authoritative_universe(token)
            spool.put("", {"dataset": "tushare_stock_basic", "rows": authority})
            for exchange, market in markets.items():
                tdx = {row["code"]: row for row in market["instruments"]}
                market["instruments"] = [
                    {**tdx.get(row["code"], {}), **row}
                    for row in authority
                    if row["exchange"] == exchange
                ]
                market["missing_in_tdx"] = [
                    row["code"] for row in market["instruments"] if row["code"] not in tdx
                ]
            verification, authority_error = "tushare_stock_basic", None
        except Exception as error:
            authority_error = type(error).__name__
    now = datetime.now(UTC).isoformat()
    universe = {
        "observed_at": now,
        "verification": verification,
        "authority_error": authority_error,
        "markets": markets,
        "instruments": [row for market in markets.values() for row in market["instruments"]],
    }
    spool.put(
        "/internal/v1/market/reports",
        {"batch_id": str(uuid4()), "kind": "universe", "observed_at": now, "body": universe},
        checkpoint=("universe", universe),
    )
    return universe
