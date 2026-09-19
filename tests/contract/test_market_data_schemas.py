import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

CONTRACT_ROOT = Path(__file__).parents[2] / "packages" / "contracts"
SCHEMA_ROOT = CONTRACT_ROOT / "jsonschema"


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_ROOT / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_market_quote_contract_accepts_complete_quote() -> None:
    validator("market-quote-v1.json").validate(
        {
            "exchange": "SSE",
            "symbol": "600519",
            "source_time": "2026-09-20T01:31:02Z",
            "collected_at": "2026-09-20T01:31:02.412Z",
            "last_price": "1468.20",
            "previous_close": "1450.21",
            "open_price": "1458.00",
            "high_price": "1472.50",
            "low_price": "1456.80",
            "volume": "1023400",
            "amount": "1502340000.00",
            "bids": [{"price": "1468.10", "quantity": "2300"}],
            "asks": [{"price": "1468.30", "quantity": "1200"}],
            "provider": "mootdx",
            "source_id": "tdx-primary",
            "payload_hash": f"sha256:{'a' * 64}",
            "quality_status": "healthy",
            "schema_version": 1,
        }
    )


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (
            "market-transaction-v1.json",
            {
                "exchange": "SZSE",
                "symbol": "000001",
                "event_time": "2026-09-20T01:31:02Z",
                "price": "11.20",
                "quantity": "100",
                "side": "buy",
                "source_offset": 0,
                "provider": "mootdx",
                "source_id": "tdx-primary",
                "payload_hash": f"sha256:{'b' * 64}",
                "coverage_status": "partial",
                "schema_version": 1,
            },
        ),
        (
            "market-bar-v1.json",
            {
                "exchange": "BSE",
                "symbol": "430047",
                "interval": "1m",
                "adjustment": "none",
                "event_time": "2026-09-20T01:31:00Z",
                "open": "10.00",
                "high": "10.20",
                "low": "9.90",
                "close": "10.10",
                "volume": "1000",
                "amount": "10100",
                "provider": "tushare",
                "payload_hash": f"sha256:{'c' * 64}",
                "schema_version": 1,
            },
        ),
    ],
)
def test_market_history_contracts_accept_valid_payloads(
    schema: str,
    payload: dict[str, object],
) -> None:
    validator(schema).validate(payload)


def test_market_quote_contract_rejects_missing_source_time() -> None:
    payload = {
        "exchange": "SSE",
        "symbol": "600519",
        "collected_at": "2026-09-20T01:31:02Z",
    }

    with pytest.raises(ValidationError):
        validator("market-quote-v1.json").validate(payload)


def test_asyncapi_declares_market_data_topics() -> None:
    document = yaml.safe_load((CONTRACT_ROOT / "asyncapi.yaml").read_text())
    addresses = {channel["address"] for channel in document["channels"].values()}

    assert {
        "market.raw.received.v1",
        "market.quote.updated.v1",
    } <= addresses
