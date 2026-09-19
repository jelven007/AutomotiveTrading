from __future__ import annotations

import secrets
from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator

from instrument_market.api.health import get_clickhouse_client
from instrument_market.config import get_settings
from instrument_market.db import get_engine
from instrument_market.errors import ServiceError
from instrument_market.services.quotes import QuoteIngestionService
from instrument_market.storage.receipts import ReceiptStore

router = APIRouter(prefix="/internal/v1/market", tags=["market-ingestion"])


class QuoteBatch(BaseModel):
    batch_id: UUID
    exchange: Literal["SSE", "SZSE", "BSE"]
    trade_date: date | None = None
    source_id: str = Field(min_length=1, max_length=128)
    collected_at: datetime
    quotes: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("collected_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")
        return value


def require_service_token(
    provided_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> None:
    expected = get_settings().ingest_service_token.get_secret_value()
    if not expected:
        raise ServiceError(
            code="market.ingest_not_configured",
            message="Market ingestion token is not configured",
            status_code=503,
        )
    if provided_token is None or not secrets.compare_digest(provided_token, expected):
        raise ServiceError(
            code="auth.invalid",
            message="Internal service token is invalid",
            status_code=401,
        )


@lru_cache
def get_ingestion_service() -> QuoteIngestionService:
    settings = get_settings()
    return QuoteIngestionService(
        get_clickhouse_client(),
        stale_after_seconds=settings.quote_stale_after_seconds,
        receipts=ReceiptStore(get_engine()),
    )


@router.post(
    "/quotes",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_service_token)],
)
def ingest_quotes(payload: QuoteBatch) -> dict[str, Any]:
    return get_ingestion_service().ingest(
        batch_id=str(payload.batch_id),
        exchange=payload.exchange,
        trade_date=payload.trade_date.isoformat() if payload.trade_date else None,
        source_id=payload.source_id,
        collected_at=payload.collected_at,
        payloads=payload.quotes,
        metadata=payload.metadata,
    )


class CollectorReport(BaseModel):
    batch_id: UUID
    kind: Literal["universe", "coverage"]
    observed_at: datetime
    body: dict[str, Any]


@router.post("/reports", dependencies=[Depends(require_service_token)])
def receive_report(payload: CollectorReport) -> dict[str, Any]:
    import json

    def persist() -> dict[str, Any]:
        get_clickhouse_client().insert_json_each_row(
            "collector_report",
            [
                {
                    "batch_id": str(payload.batch_id),
                    "kind": payload.kind,
                    "observed_at": payload.observed_at,
                    "body": json.dumps(payload.body, ensure_ascii=False),
                }
            ],
        )
        return {"batch_id": str(payload.batch_id), "accepted": 1}

    return get_ingestion_service().receipts.apply(
        str(payload.batch_id),
        payload.model_dump(mode="json"),
        persist,
    )
