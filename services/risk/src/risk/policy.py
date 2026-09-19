from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AccountScope(StrEnum):
    SPOT = "spot"
    CROSS_MARGIN = "cross_margin"
    ISOLATED_MARGIN = "isolated_margin"
    USDM_FUTURES = "usdm_futures"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class RiskPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_scopes: list[AccountScope] = Field(min_length=1)
    allowed_symbols: list[str] = Field(min_length=1)
    allowed_sources: list[str] = Field(min_length=1)
    max_order_notional: Decimal = Field(gt=0)
    max_daily_notional: Decimal = Field(gt=0)
    max_position_notional: Decimal = Field(gt=0)
    max_futures_leverage: int = Field(ge=1, le=125)
    min_margin_level: Decimal = Field(gt=0)
    min_liquidation_distance: Decimal = Field(ge=0, le=1)
    max_adl_quantile: int = Field(ge=0, le=4)
    max_snapshot_age_seconds: int = Field(ge=1, le=60)

    @model_validator(mode="after")
    def normalize_lists(self) -> "RiskPolicy":
        self.allowed_scopes = list(dict.fromkeys(self.allowed_scopes))
        self.allowed_symbols = list(
            dict.fromkeys(symbol.strip().upper() for symbol in self.allowed_symbols)
        )
        self.allowed_sources = list(
            dict.fromkeys(source.strip().lower() for source in self.allowed_sources)
        )
        return self


class OrderRiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_scope: AccountScope
    symbol: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9]+$")
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    reduce_only: bool = False
    source: str = Field(min_length=1, max_length=32)
    leverage: int | None = Field(default=None, ge=1, le=125)
    account_id: str | None = Field(default=None, max_length=36)
    time_in_force: str | None = Field(default=None, max_length=8)
    position_side: str | None = Field(default=None, max_length=8)
    margin_side_effect: str = Field(default="none", max_length=32)

    @model_validator(mode="after")
    def normalize_order(self) -> "OrderRiskInput":
        self.symbol = self.symbol.upper()
        self.source = self.source.lower()
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit price is required for limit orders")
        if self.account_scope is not AccountScope.USDM_FUTURES and self.reduce_only:
            raise ValueError("reduceOnly is only valid for futures")
        return self


class RiskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    mark_price: Decimal = Field(gt=0)
    available_balance: Decimal = Field(ge=0)
    daily_traded_notional: Decimal = Field(ge=0)
    current_position_notional: Decimal = Field(ge=0)
    margin_level: Decimal | None = Field(default=None, ge=0)
    liquidation_distance: Decimal | None = Field(default=None, ge=0, le=1)
    adl_quantile: int | None = Field(default=None, ge=0, le=4)
    current_leverage: int | None = Field(default=None, ge=1, le=125)
    protection_mode: bool = False


class RiskDecision(BaseModel):
    approved: bool
    reasons: list[str]
    order_notional: Decimal
    projected_daily_notional: Decimal
    projected_position_notional: Decimal


class RiskEvaluator:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))

    def evaluate(
        self,
        policy: RiskPolicy,
        order: OrderRiskInput,
        snapshot: RiskSnapshot,
    ) -> RiskDecision:
        reasons: list[str] = []
        as_of = snapshot.as_of if snapshot.as_of.tzinfo else snapshot.as_of.replace(tzinfo=UTC)
        age_seconds = (self.clock() - as_of).total_seconds()
        if age_seconds < -1 or age_seconds > policy.max_snapshot_age_seconds:
            reasons.append("snapshot_stale")

        if order.account_scope not in policy.allowed_scopes:
            reasons.append("scope_not_allowed")
        if order.symbol not in policy.allowed_symbols:
            reasons.append("symbol_not_allowed")
        if order.source not in policy.allowed_sources:
            reasons.append("source_not_allowed")

        price = order.limit_price or snapshot.mark_price
        order_notional = order.quantity * price
        projected_daily = snapshot.daily_traded_notional + order_notional
        projected_position = (
            max(Decimal(0), snapshot.current_position_notional - order_notional)
            if order.reduce_only
            else snapshot.current_position_notional + order_notional
        )

        if order_notional > policy.max_order_notional:
            reasons.append("order_notional_exceeded")
        if projected_daily > policy.max_daily_notional:
            reasons.append("daily_notional_exceeded")
        if projected_position > policy.max_position_notional:
            reasons.append("position_notional_exceeded")
        if (
            order.account_scope is AccountScope.SPOT
            and order.side is OrderSide.BUY
            and order_notional > snapshot.available_balance
        ):
            reasons.append("insufficient_available_balance")

        if order.account_scope in {
            AccountScope.CROSS_MARGIN,
            AccountScope.ISOLATED_MARGIN,
        } and (snapshot.margin_level is None or snapshot.margin_level < policy.min_margin_level):
            reasons.append("margin_level_too_low")

        if order.account_scope is AccountScope.USDM_FUTURES:
            leverage = order.leverage or snapshot.current_leverage
            if leverage is None or leverage > policy.max_futures_leverage:
                reasons.append("futures_leverage_exceeded")
            if (
                snapshot.liquidation_distance is None
                or snapshot.liquidation_distance < policy.min_liquidation_distance
            ):
                reasons.append("liquidation_distance_too_low")
            if snapshot.adl_quantile is None or snapshot.adl_quantile > policy.max_adl_quantile:
                reasons.append("adl_risk_too_high")

        if snapshot.protection_mode and not (
            order.account_scope is AccountScope.USDM_FUTURES and order.reduce_only
        ):
            reasons.append("protection_mode")

        return RiskDecision(
            approved=not reasons,
            reasons=reasons,
            order_notional=order_notional,
            projected_daily_notional=projected_daily,
            projected_position_notional=projected_position,
        )
