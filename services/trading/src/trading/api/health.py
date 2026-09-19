from fastapi import APIRouter
from fastapi.responses import JSONResponse

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
