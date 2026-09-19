from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from instrument_market.pipeline.envelope import RawEnvelope, canonical_payload_hash
from instrument_market.providers.models import Dataset, ProviderName


def test_canonical_payload_hash_is_stable_for_key_order_and_decimal() -> None:
    first = {"price": Decimal("12.30"), "volume": 100, "nested": {"b": 2, "a": 1}}
    second = {"nested": {"a": 1, "b": 2}, "volume": 100, "price": Decimal("12.30")}

    assert canonical_payload_hash(first) == canonical_payload_hash(second)


def test_raw_envelope_create_preserves_source_metadata() -> None:
    source_time = datetime(2026, 9, 20, 1, 31, 2, tzinfo=UTC)
    collected_at = datetime(2026, 9, 20, 1, 31, 2, 412000, tzinfo=UTC)

    envelope = RawEnvelope.create(
        provider=ProviderName.MOOTDX,
        dataset=Dataset.QUOTE,
        market="CN",
        exchange="SSE",
        symbol="600519",
        source_time=source_time,
        collected_at=collected_at,
        source_id="tdx-primary",
        request={"batch_id": "batch-1"},
        payload={"price": Decimal("1468.20")},
    )

    assert envelope.provider is ProviderName.MOOTDX
    assert envelope.dataset is Dataset.QUOTE
    assert envelope.source_time == source_time
    assert envelope.collected_at == collected_at
    assert envelope.payload_hash.startswith("sha256:")
    assert envelope.schema_version == 1


def test_raw_envelope_rejects_naive_timestamps() -> None:
    naive = datetime(2026, 9, 20, 9, 31, 2)

    with pytest.raises(ValueError, match="timezone-aware"):
        RawEnvelope.create(
            provider=ProviderName.MOOTDX,
            dataset=Dataset.QUOTE,
            market="CN",
            exchange="SSE",
            symbol="600519",
            source_time=naive,
            collected_at=naive,
            source_id="tdx-primary",
            request={},
            payload={"price": "1.00"},
        )
