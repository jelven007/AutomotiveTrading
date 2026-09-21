from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from trading.api.dependencies import (
    get_binance_overview_cache,
    get_binance_runtime_manager,
)
from trading.binance_runtime.manager import SingleNautilusRuntimeManager
from trading.binance_runtime.overview import (
    BinanceOverview,
    BinanceOverviewCache,
    BinanceOverviewService,
)
from trading.db import get_session
from trading.errors import ServiceError
from trading.security import Principal, get_principal

router = APIRouter(prefix="/api/v1/trading/binance", tags=["binance-overview"])


def get_binance_overview_service(
    session: Annotated[Session, Depends(get_session)],
    runtime_manager: Annotated[
        SingleNautilusRuntimeManager,
        Depends(get_binance_runtime_manager),
    ],
    cache: Annotated[BinanceOverviewCache, Depends(get_binance_overview_cache)],
) -> BinanceOverviewService:
    return BinanceOverviewService(session, runtime_manager, cache=cache)


@router.get("/overview", response_model=BinanceOverview)
async def get_binance_overview(
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[BinanceOverviewService, Depends(get_binance_overview_service)],
    refresh: Annotated[bool, Query()] = False,
) -> BinanceOverview:
    try:
        return await service.get(principal.tenant_id, refresh=refresh)
    except LookupError as error:
        raise ServiceError(
            code="binance.account_missing",
            message=str(error),
            status_code=404,
        ) from error


__all__ = [
    "get_binance_overview_cache",
    "get_binance_overview_service",
    "router",
]
