from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from instrument_market.pipeline.envelope import RawEnvelope
from instrument_market.pipeline.normalize import _source_time, normalize_quote
from instrument_market.pipeline.quality import evaluate_quote
from instrument_market.providers.models import Dataset, ProviderName
from instrument_market.storage.clickhouse import quote_row, raw_quote_row
from instrument_market.storage.receipts import ReceiptStore


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
        receipts: ReceiptStore | None = None,
        clock: Any = None,
    ) -> None:
        self.sink = sink
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self.receipts = receipts or ReceiptStore()
        self.clock = clock or (lambda: datetime.now(UTC))

    def ingest(
        self,
        *,
        batch_id: str,
        exchange: str,
        trade_date: str | None,
        source_id: str,
        collected_at: datetime,
        payloads: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if collected_at.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")
        body = {
            "exchange": exchange,
            "trade_date": trade_date,
            "source_id": source_id,
            "collected_at": collected_at.isoformat(),
            "quotes": payloads,
            "metadata": metadata or {},
        }
        return self.receipts.apply(
            batch_id,
            body,
            lambda: self._persist(
                batch_id, exchange, trade_date, source_id, collected_at, payloads, metadata or {}
            ),
        )

    def _persist(
        self,
        batch_id: str,
        exchange: str,
        trade_date: str | None,
        source_id: str,
        collected_at: datetime,
        payloads: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        raw_rows: list[dict[str, Any]] = []
        standard_rows: list[dict[str, Any]] = []
        statuses: Counter[str] = Counter()
        rejected: list[dict[str, Any]] = []
        now = self.clock()
        for index, payload in enumerate(payloads):
            try:
                source_time = _source_time(
                    trade_date=trade_date,
                    server_time=payload.get("servertime"),
                    fallback=collected_at,
                )
            except (ValueError, TypeError):
                source_time = datetime(1970, 1, 1, tzinfo=UTC)
            envelope = RawEnvelope.create(
                provider=ProviderName.MOOTDX,
                dataset=Dataset.QUOTE,
                market="CN",
                exchange=exchange,
                symbol=str(payload.get("code") or payload.get("symbol") or ""),
                source_time=source_time,
                collected_at=collected_at,
                source_id=source_id,
                request={"batch_id": batch_id, "row_index": index},
                payload=payload,
            )
            envelope = replace(
                envelope,
                event_id=str(uuid5(NAMESPACE_URL, f"{batch_id}/{index}")),
            )
            raw_row = raw_quote_row(envelope)
            raw_row.update(
                batch_id=batch_id,
                row_index=index,
                metadata_json=_json({**metadata, "trade_date": trade_date}),
            )
            raw_rows.append(raw_row)
        # 原始层先完整提交。坏行只影响标准层而不影响取证与其余证券。
        self.sink.insert_json_each_row("market_quote_raw", raw_rows)
        seen: set[str] = set()
        for index, payload in enumerate(payloads):
            try:
                symbol = str(payload.get("code") or payload.get("symbol") or "")
                if metadata.get("requested") is not None and symbol not in metadata["requested"]:
                    raise ValueError("unexpected symbol")
                if (
                    "market" in payload
                    and payload["market"] != {"SZSE": 0, "SSE": 1, "BSE": 2}[exchange]
                ):
                    raise ValueError("unexpected market")
                if symbol in seen:
                    raise ValueError("duplicate symbol")
                seen.add(symbol)
                normalized = normalize_quote(
                    payload,
                    exchange=exchange,
                    trade_date=trade_date,
                    collected_at=collected_at,
                    source_id=source_id,
                    payload_hash=raw_rows[index]["payload_hash"],
                    metadata=metadata,
                )
            except (ValueError, TypeError, ArithmeticError) as error:
                rejected.append({"row_index": index, "reason": str(error)})
                continue
            quality = evaluate_quote(
                normalized,
                now=now,
                stale_after=self.stale_after,
            )
            standard_row = quote_row(normalized)
            standard_row["quality_status"] = quality.status.value
            standard_row["quality_reasons"] = _json(quality.reasons)
            standard_row["batch_id"] = batch_id
            standard_row["metadata_json"] = _json(metadata)
            standard_rows.append(standard_row)
            statuses[quality.status.value] += 1

        self.sink.insert_json_each_row("market_quote", standard_rows)
        return {
            "batch_id": batch_id,
            "accepted": len(standard_rows),
            "received": len(payloads),
            "rejected": len(rejected),
            "errors": rejected,
            "quality": dict(sorted(statuses.items())),
        }


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
