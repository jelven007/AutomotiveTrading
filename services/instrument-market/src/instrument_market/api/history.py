from datetime import date
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query

from instrument_market.api.health import get_clickhouse_client
from instrument_market.services.history import HistoryViewService

router = APIRouter(prefix="/api/v1/market", tags=["market-history"])
Exchange = Literal["SSE", "SZSE"]
Symbol = Annotated[str, Path(pattern=r"^[0-9]{6}$")]


@lru_cache
def get_history_view_service() -> HistoryViewService:
    return HistoryViewService(get_clickhouse_client())


@router.get("/bars/{exchange}/{symbol}")
def bars(
    exchange: Exchange,
    symbol: Symbol,
    interval: Literal["1d"] = "1d",
    limit: Annotated[int, Query(ge=1, le=800)] = 240,
) -> dict[str, Any]:
    return get_history_view_service().bars(
        exchange=exchange,
        symbol=symbol,
        interval=interval,
        limit=limit,
    )


@router.get("/minutes/{exchange}/{symbol}")
def minutes(
    exchange: Exchange,
    symbol: Symbol,
    trade_date: date | None = None,
) -> dict[str, Any]:
    return get_history_view_service().minutes(
        exchange=exchange,
        symbol=symbol,
        trade_date=trade_date.isoformat() if trade_date else None,
    )


@router.get("/transactions/{exchange}/{symbol}")
def transactions(
    exchange: Exchange,
    symbol: Symbol,
    trade_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    return get_history_view_service().transactions(
        exchange=exchange,
        symbol=symbol,
        trade_date=trade_date.isoformat() if trade_date else None,
        limit=limit,
    )
