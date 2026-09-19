from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from risk.policy import (
    AccountScope,
    OrderRiskInput,
    RiskEvaluator,
    RiskPolicy,
    RiskSnapshot,
)

NOW = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)


def policy(**overrides: object) -> RiskPolicy:
    values: dict[str, object] = {
        "allowed_scopes": list(AccountScope),
        "allowed_symbols": ["BTCUSDT", "ETHUSDT"],
        "allowed_sources": ["manual"],
        "max_order_notional": "1000",
        "max_daily_notional": "5000",
        "max_position_notional": "3000",
        "max_futures_leverage": 10,
        "min_margin_level": "1.5",
        "min_liquidation_distance": "0.10",
        "max_adl_quantile": 2,
        "max_snapshot_age_seconds": 5,
    }
    values.update(overrides)
    return RiskPolicy.model_validate(values)


def order(**overrides: object) -> OrderRiskInput:
    values: dict[str, object] = {
        "account_scope": "spot",
        "symbol": "BTCUSDT",
        "side": "buy",
        "order_type": "limit",
        "quantity": "0.01",
        "limit_price": "50000",
        "reduce_only": False,
        "source": "manual",
        "leverage": None,
    }
    values.update(overrides)
    return OrderRiskInput.model_validate(values)


def snapshot(**overrides: object) -> RiskSnapshot:
    values: dict[str, object] = {
        "as_of": NOW,
        "mark_price": "50000",
        "available_balance": "1000",
        "daily_traded_notional": "100",
        "current_position_notional": "500",
        "margin_level": "2",
        "liquidation_distance": "0.30",
        "adl_quantile": 1,
        "protection_mode": False,
    }
    values.update(overrides)
    return RiskSnapshot.model_validate(values)


def evaluate(
    *,
    risk_policy: RiskPolicy | None = None,
    order_input: OrderRiskInput | None = None,
    risk_snapshot: RiskSnapshot | None = None,
):
    return RiskEvaluator(clock=lambda: NOW).evaluate(
        risk_policy or policy(),
        order_input or order(),
        risk_snapshot or snapshot(),
    )


def test_approves_order_within_all_limits() -> None:
    decision = evaluate()

    assert decision.approved is True
    assert decision.reasons == []
    assert decision.order_notional == Decimal("500")


@pytest.mark.parametrize(
    ("risk_policy", "order_input", "risk_snapshot", "reason"),
    [
        (
            policy(allowed_symbols=["ETHUSDT"]),
            order(),
            snapshot(),
            "symbol_not_allowed",
        ),
        (
            policy(max_order_notional="499"),
            order(),
            snapshot(),
            "order_notional_exceeded",
        ),
        (
            policy(max_daily_notional="599"),
            order(),
            snapshot(),
            "daily_notional_exceeded",
        ),
        (
            policy(),
            order(),
            snapshot(available_balance="499"),
            "insufficient_available_balance",
        ),
        (
            policy(),
            order(account_scope="cross_margin"),
            snapshot(margin_level="1.49"),
            "margin_level_too_low",
        ),
        (
            policy(),
            order(account_scope="usdm_futures", leverage=11),
            snapshot(),
            "futures_leverage_exceeded",
        ),
        (
            policy(),
            order(account_scope="usdm_futures", leverage=5),
            snapshot(liquidation_distance="0.09"),
            "liquidation_distance_too_low",
        ),
        (
            policy(),
            order(account_scope="usdm_futures", leverage=5),
            snapshot(adl_quantile=3),
            "adl_risk_too_high",
        ),
        (
            policy(),
            order(),
            snapshot(as_of=NOW - timedelta(seconds=6)),
            "snapshot_stale",
        ),
    ],
)
def test_rejects_orders_that_break_a_policy(
    risk_policy: RiskPolicy,
    order_input: OrderRiskInput,
    risk_snapshot: RiskSnapshot,
    reason: str,
) -> None:
    decision = evaluate(
        risk_policy=risk_policy,
        order_input=order_input,
        risk_snapshot=risk_snapshot,
    )

    assert decision.approved is False
    assert reason in decision.reasons


def test_protection_mode_only_allows_explicit_futures_reduction() -> None:
    opening = evaluate(
        order_input=order(account_scope="usdm_futures", leverage=5),
        risk_snapshot=snapshot(protection_mode=True),
    )
    reducing = evaluate(
        order_input=order(
            account_scope="usdm_futures",
            side="sell",
            leverage=5,
            reduce_only=True,
        ),
        risk_snapshot=snapshot(protection_mode=True),
    )

    assert opening.approved is False
    assert "protection_mode" in opening.reasons
    assert reducing.approved is True
