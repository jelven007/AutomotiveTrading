from datetime import UTC, datetime, timedelta

import pytest
from risk.authorizations import (
    AuthorizationError,
    RiskAuthorizationService,
)
from risk.models import RiskApproval
from risk.policy import AccountScope, RiskPolicy
from sqlalchemy import select
from sqlalchemy.orm import Session

NOW = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)


def policy() -> RiskPolicy:
    return RiskPolicy(
        allowed_scopes=list(AccountScope),
        allowed_symbols=["BTCUSDT"],
        allowed_sources=["manual"],
        max_order_notional="1000",
        max_daily_notional="5000",
        max_position_notional="3000",
        max_futures_leverage=10,
        min_margin_level="1.5",
        min_liquidation_distance="0.10",
        max_adl_quantile=2,
        max_snapshot_age_seconds=5,
    )


def order(quantity: str = "0.01") -> dict[str, object]:
    return {
        "account_scope": "spot",
        "symbol": "BTCUSDT",
        "side": "buy",
        "order_type": "limit",
        "quantity": quantity,
        "limit_price": "50000",
        "reduce_only": False,
        "source": "manual",
        "leverage": None,
    }


def snapshot() -> dict[str, object]:
    return {
        "as_of": NOW.isoformat(),
        "mark_price": "50000",
        "available_balance": "1000",
        "daily_traded_notional": "100",
        "current_position_notional": "500",
        "margin_level": "2",
        "liquidation_distance": "0.30",
        "adl_quantile": 1,
        "protection_mode": False,
    }


def service(session: Session, now: list[datetime]) -> RiskAuthorizationService:
    instance = RiskAuthorizationService(session, clock=lambda: now[0])
    instance.set_policy("tenant-a", policy())
    return instance


def test_approved_token_is_hashed_and_consumed_once(session: Session) -> None:
    now = [NOW]
    authorization_service = service(session, now)

    issued = authorization_service.issue(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(),
        snapshot_payload=snapshot(),
    )

    assert issued.approved is True
    assert issued.approval_token is not None
    stored = session.scalar(select(RiskApproval))
    assert stored is not None
    assert issued.approval_token not in repr(stored)
    assert issued.approval_token not in stored.token_hash

    verified = authorization_service.verify_and_consume(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(),
        approval_token=issued.approval_token,
    )
    assert verified is True
    with pytest.raises(AuthorizationError, match="already consumed"):
        authorization_service.verify_and_consume(
            tenant_id="tenant-a",
            account_id="account-a",
            order_payload=order(),
            approval_token=issued.approval_token,
        )


def test_token_is_bound_to_tenant_account_and_order(session: Session) -> None:
    now = [NOW]
    authorization_service = service(session, now)
    issued = authorization_service.issue(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(),
        snapshot_payload=snapshot(),
    )
    assert issued.approval_token is not None

    for tenant_id, account_id, payload in [
        ("tenant-b", "account-a", order()),
        ("tenant-a", "account-b", order()),
        ("tenant-a", "account-a", order(quantity="0.02")),
    ]:
        with pytest.raises(AuthorizationError):
            authorization_service.verify_and_consume(
                tenant_id=tenant_id,
                account_id=account_id,
                order_payload=payload,
                approval_token=issued.approval_token,
            )

    assert authorization_service.verify_and_consume(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(),
        approval_token=issued.approval_token,
    )


def test_expired_token_is_rejected(session: Session) -> None:
    now = [NOW]
    authorization_service = service(session, now)
    issued = authorization_service.issue(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(),
        snapshot_payload=snapshot(),
    )
    assert issued.approval_token is not None
    now[0] = NOW + timedelta(seconds=61)

    with pytest.raises(AuthorizationError, match="expired"):
        authorization_service.verify_and_consume(
            tenant_id="tenant-a",
            account_id="account-a",
            order_payload=order(),
            approval_token=issued.approval_token,
        )


def test_rejected_decision_does_not_issue_token(session: Session) -> None:
    now = [NOW]
    authorization_service = service(session, now)

    issued = authorization_service.issue(
        tenant_id="tenant-a",
        account_id="account-a",
        order_payload=order(quantity="1"),
        snapshot_payload=snapshot(),
    )

    assert issued.approved is False
    assert issued.approval_token is None
    assert "order_notional_exceeded" in issued.reasons
