import asyncio
from collections.abc import Awaitable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from trading.api.dependencies import get_binance_runtime_manager
from trading.binance_runtime.manager import SingleNautilusRuntimeManager
from trading.db import database_is_ready

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def readiness() -> dict[str, str] | JSONResponse:
    if not database_is_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}


@router.get("/api/v1/trading/health", response_model=None)
def service_health() -> dict[str, str] | JSONResponse:
    if not database_is_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}


@router.get("/health/binance")
async def binance_health(
    runtime_manager: Annotated[
        SingleNautilusRuntimeManager,
        Depends(get_binance_runtime_manager),
    ],
) -> dict[str, str]:
    runtime = runtime_manager.current
    if runtime is None:
        return {"api": "ready", "spot": "unavailable", "usdm": "unavailable"}

    spot, usdm = await asyncio.gather(
        _component_status(runtime.read_spot()),
        _component_status(runtime.read_usdm()),
    )
    return {"api": "ready", "spot": spot, "usdm": usdm}


async def _component_status(
    pending: Awaitable[object],
) -> Literal["ready", "unavailable"]:
    try:
        await pending
    except Exception:
        return "unavailable"
    return "ready"
