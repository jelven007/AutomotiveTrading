from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from instrument_market.providers.models import Dataset, ProviderName


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported payload type: {type(value).__name__}")


def canonical_payload_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class RawEnvelope:
    event_id: str
    provider: ProviderName
    dataset: Dataset
    market: str
    exchange: str
    symbol: str
    source_time: datetime
    collected_at: datetime
    source_id: str
    request: dict[str, Any]
    schema_version: int
    payload_hash: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        provider: ProviderName,
        dataset: Dataset,
        market: str,
        exchange: str,
        symbol: str,
        source_time: datetime,
        collected_at: datetime,
        source_id: str,
        request: dict[str, Any],
        payload: dict[str, Any],
    ) -> RawEnvelope:
        if source_time.tzinfo is None or collected_at.tzinfo is None:
            raise ValueError("source_time and collected_at must be timezone-aware")
        return cls(
            event_id=str(uuid4()),
            provider=provider,
            dataset=dataset,
            market=market,
            exchange=exchange,
            symbol=symbol,
            source_time=source_time.astimezone(UTC),
            collected_at=collected_at.astimezone(UTC),
            source_id=source_id,
            request=request,
            schema_version=1,
            payload_hash=canonical_payload_hash(payload),
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
