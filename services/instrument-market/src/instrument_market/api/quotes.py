from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Query

from instrument_market.api.health import get_clickhouse_client
from instrument_market.config import get_settings
from instrument_market.services.market_view import MarketViewService

router = APIRouter(prefix="/api/v1/market", tags=["market-data"])


@lru_cache
def get_market_view_service() -> MarketViewService:
    return MarketViewService(get_clickhouse_client())


@router.get("/quotes/latest")
def latest_quotes(
    limit: Annotated[int, Query(ge=1, le=10_000)] = 6_000,
) -> dict[str, Any]:
    configured_limit = get_settings().max_query_rows
    return get_market_view_service().latest_quotes(limit=min(limit, configured_limit))
