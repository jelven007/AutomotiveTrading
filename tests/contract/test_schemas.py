import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = Path(__file__).parents[2] / "packages/contracts/jsonschema/model-decision-v1.json"


@pytest.fixture
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture
def valid_decision() -> dict[str, object]:
    return {
        "action": "buy",
        "confidence": 0.82,
        "target_position_pct": 0.15,
        "order_type": "limit",
        "limit_price": "12.30",
        "valid_until": "2026-09-18T07:00:00Z",
        "reasons": ["Momentum and liquidity conditions are satisfied"],
        "risk_flags": [],
    }


def test_model_decision_accepts_analysis_only_payload(
    validator: Draft202012Validator,
    valid_decision: dict[str, object],
) -> None:
    validator.validate(valid_decision)


def test_model_decision_rejects_unknown_action(
    validator: Draft202012Validator,
    valid_decision: dict[str, object],
) -> None:
    valid_decision["action"] = "short"

    with pytest.raises(ValidationError):
        validator.validate(valid_decision)


@pytest.mark.parametrize("execution_field", ["account_id", "quantity", "client_order_id"])
def test_model_decision_rejects_execution_fields(
    validator: Draft202012Validator,
    valid_decision: dict[str, object],
    execution_field: str,
) -> None:
    valid_decision[execution_field] = "forbidden"

    with pytest.raises(ValidationError):
        validator.validate(valid_decision)


def test_limit_price_must_be_a_decimal_string(
    validator: Draft202012Validator,
    valid_decision: dict[str, object],
) -> None:
    valid_decision["limit_price"] = 12.3

    with pytest.raises(ValidationError):
        validator.validate(valid_decision)
