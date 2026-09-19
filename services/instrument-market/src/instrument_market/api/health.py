from functools import lru_cache

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from instrument_market.config import get_settings
from instrument_market.db import database_is_ready
from instrument_market.storage.clickhouse import ClickHouseClient

router = APIRouter(tags=["health"])


@lru_cache
def get_clickhouse_client() -> ClickHouseClient:
    settings = get_settings()
    return ClickHouseClient(
        base_url=settings.clickhouse_url,
        database=settings.clickhouse_database,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password.get_secret_value(),
        timeout_seconds=settings.clickhouse_timeout_seconds,
    )


def clickhouse_is_ready() -> bool:
    try:
        client = get_clickhouse_client()
        return client.ping() and client.schema_is_ready()
    except Exception:
        return False


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def readiness() -> dict[str, object] | JSONResponse:
    dependencies = {
        "mysql": database_is_ready(),
        "clickhouse": clickhouse_is_ready(),
    }
    if not all(dependencies.values()):
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "dependencies": dependencies},
        )
    return {"status": "ready", "dependencies": dependencies}
