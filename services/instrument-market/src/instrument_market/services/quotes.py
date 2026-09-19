from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Protocol

from instrument_market.pipeline.envelope import RawEnvelope
from instrument_market.pipeline.normalize import normalize_quote
from instrument_market.pipeline.quality import evaluate_quote
from instrument_market.providers.models import Dataset, ProviderName
from instrument_market.storage.clickhouse import quote_row, raw_quote_row


class RowSink(Protocol):
    def insert_json_each_row(
        self,
        table: str,
        rows: list[dict[str, Any]],
    ) -> None: ...


class QuoteIngestionService:
    def __init__(
        self,
        sink: RowSink,
        *,
        stale_after_seconds: float,
    ) -> None:
        self.sink = sink
        self.stale_after = timedelta(seconds=stale_after_seconds)

    def ingest(
        self,
        *,
        batch_id: str,
        exchange: str,
        trade_date: str,
        source_id: str,
        collected_at: datetime,
        payloads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if collected_at.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")

        raw_rows: list[dict[str, Any]] = []
        standard_rows: list[dict[str, Any]] = []
        statuses: Counter[str] = Counter()
        for payload in payloads:
            normalized = normalize_quote(
                payload,
                exchange=exchange,
                trade_date=trade_date,
                collected_at=collected_at,
                source_id=source_id,
            )
            envelope = RawEnvelope.create(
                provider=ProviderName.MOOTDX,
                dataset=Dataset.QUOTE,
                market="CN",
                exchange=exchange,
                symbol=normalized.symbol,
                source_time=normalized.source_time,
                collected_at=collected_at,
                source_id=source_id,
                request={"batch_id": batch_id},
                payload=payload,
            )
            normalized = replace(normalized, payload_hash=envelope.payload_hash)
            quality = evaluate_quote(
                normalized,
                now=collected_at,
                stale_after=self.stale_after,
            )
            raw_rows.append(raw_quote_row(envelope))
            standard_row = quote_row(normalized)
            standard_row["quality_status"] = quality.status.value
            standard_rows.append(standard_row)
            statuses[quality.status.value] += 1

        self.sink.insert_json_each_row("market_quote_raw", raw_rows)
        self.sink.insert_json_each_row("market_quote", standard_rows)
        return {
            "batch_id": batch_id,
            "accepted": len(standard_rows),
            "quality": dict(sorted(statuses.items())),
        }
