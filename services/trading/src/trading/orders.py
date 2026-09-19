import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.binance.client import BinanceCredentials
from trading.binance.errors import BinanceConnectorError, BinanceWriteTimeout
from trading.models import (
    AccountScopeType,
    AccountStatus,
    CredentialType,
    KillSwitch,
    OrderStatus,
    TradingAccount,
    TradingAccountScope,
    TradingOrder,
    utc_now,
)
from trading.outbox import SqlOutboxPublisher
from trading.risk import RiskAuthorizer
from trading.secrets import SecretBackend


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class PositionSide(StrEnum):
    BOTH = "both"
    LONG = "long"
    SHORT = "short"


class MarginSideEffect(StrEnum):
    NONE = "none"
    BORROW = "borrow"
    REPAY = "repay"
    AUTO_BORROW_REPAY = "auto_borrow_repay"


class OrderSource(StrEnum):
    MANUAL = "manual"
    STRATEGY = "strategy"


class OrderCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=36)
    account_scope: AccountScopeType
    symbol: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9]+$")
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    time_in_force: str | None = Field(default=None, pattern=r"^(GTC|IOC|FOK)$")
    position_side: PositionSide | None = None
    reduce_only: bool = False
    margin_side_effect: MarginSideEffect = MarginSideEffect.NONE
    source: OrderSource = OrderSource.MANUAL

    @model_validator(mode="after")
    def validate_order_semantics(self) -> "OrderCommand":
        self.symbol = self.symbol.upper()
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit price is required for limit orders")
        if self.order_type is OrderType.LIMIT and self.time_in_force is None:
            raise ValueError("time in force is required for limit orders")
        if self.account_scope is not AccountScopeType.USDM_FUTURES and (
            self.position_side is not None or self.reduce_only
        ):
            raise ValueError("position semantics are only valid for futures")
        if (
            self.account_scope
            not in {
                AccountScopeType.CROSS_MARGIN,
                AccountScopeType.ISOLATED_MARGIN,
            }
            and self.margin_side_effect is not MarginSideEffect.NONE
        ):
            raise ValueError("margin side effects are only valid for margin orders")
        return self


class OrderExecutionResult(BaseModel):
    broker_order_id: str
    status: OrderStatus
    filled_quantity: str = "0"
    average_price: str | None = None


class OrderView(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    client_order_id: str
    broker_order_id: str | None
    account_scope: AccountScopeType
    symbol: str
    side: OrderSide
    position_side: PositionSide | None
    order_type: OrderType
    quantity: str
    limit_price: str | None
    reduce_only: bool
    margin_side_effect: MarginSideEffect
    filled_quantity: str
    average_price: str | None
    status: OrderStatus
    source: OrderSource
    error_code: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExecutionConnector(Protocol):
    def submit_order(
        self,
        *,
        scope: AccountScopeType,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: str,
        limit_price: str | None,
        time_in_force: str | None,
        position_side: PositionSide | None,
        reduce_only: bool,
        margin_side_effect: MarginSideEffect,
        client_order_id: str,
        credentials: BinanceCredentials,
    ) -> OrderExecutionResult: ...

    def cancel_order(
        self,
        *,
        scope: AccountScopeType,
        symbol: str,
        client_order_id: str,
        credentials: BinanceCredentials,
    ) -> OrderExecutionResult: ...


class IdempotencyConflictError(RuntimeError):
    pass


class TradingGuardError(RuntimeError):
    pass


class OrderService:
    def __init__(
        self,
        session: Session,
        secret_backend: SecretBackend,
        connector: ExecutionConnector,
        risk_authorizer: RiskAuthorizer,
    ) -> None:
        self.session = session
        self.secret_backend = secret_backend
        self.connector = connector
        self.risk_authorizer = risk_authorizer
        self.outbox = SqlOutboxPublisher(session)

    def submit(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
        idempotency_key: str,
        risk_approval_token: str,
        command: OrderCommand,
    ) -> OrderView:
        self._require_trader(actor_roles)
        self._require_recent_mfa(mfa_verified_at)
        if not idempotency_key or len(idempotency_key) > 80:
            raise ValueError("a valid idempotency key is required")

        fingerprint = self._fingerprint(command)
        existing = self.session.scalar(
            select(TradingOrder).where(
                TradingOrder.tenant_id == tenant_id,
                TradingOrder.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("idempotency key payload conflict")
            return self._view(existing)

        account = self._account(tenant_id, command.account_id)
        self._validate_account(account)
        self._validate_scope(tenant_id, account.id, command)
        self._ensure_kill_switch_inactive(tenant_id, account.id)
        approved = self.risk_authorizer.authorize(
            tenant_id=tenant_id,
            account_id=account.id,
            order=command.model_dump(mode="json"),
            approval_token=risk_approval_token,
        )
        if not approved:
            raise TradingGuardError("risk approval is required")

        credentials = self._credentials(account)
        client_order_id = f"qt_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:29]}"
        order = TradingOrder(
            tenant_id=tenant_id,
            account_id=account.id,
            client_order_id=client_order_id,
            account_scope=command.account_scope,
            symbol=command.symbol,
            side=command.side.value,
            position_side=command.position_side.value if command.position_side else None,
            order_type=command.order_type.value,
            time_in_force=command.time_in_force,
            quantity=str(command.quantity),
            limit_price=str(command.limit_price) if command.limit_price is not None else None,
            reduce_only=command.reduce_only,
            margin_side_effect=command.margin_side_effect.value,
            source=command.source.value,
            status=OrderStatus.PENDING_SUBMIT,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        # 先持久化意图, 再执行不可回滚的交易所写请求。
        self.session.add(order)
        self.session.flush()
        self._publish_order(order, "trading.order.submission_requested")
        self.session.commit()

        try:
            result = self.connector.submit_order(
                scope=command.account_scope,
                symbol=command.symbol,
                side=command.side,
                order_type=command.order_type,
                quantity=str(command.quantity),
                limit_price=(str(command.limit_price) if command.limit_price is not None else None),
                time_in_force=command.time_in_force,
                position_side=command.position_side,
                reduce_only=command.reduce_only,
                margin_side_effect=command.margin_side_effect,
                client_order_id=client_order_id,
                credentials=credentials,
            )
        except BinanceWriteTimeout as error:
            order.status = OrderStatus.UNKNOWN
            order.error_code = error.code
        except BinanceConnectorError as error:
            order.status = OrderStatus.REJECTED
            order.error_code = error.code
        else:
            order.broker_order_id = result.broker_order_id
            order.status = result.status
            order.filled_quantity = result.filled_quantity
            order.average_price = result.average_price
            order.submitted_at = utc_now()
        self._publish_order(order, "trading.order.status_changed")
        self.session.commit()
        return self._view(order)

    def get(self, tenant_id: str, order_id: str) -> OrderView:
        return self._view(self._order(tenant_id, order_id))

    def cancel(
        self,
        *,
        tenant_id: str,
        order_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
        idempotency_key: str,
    ) -> OrderView:
        self._require_trader(actor_roles)
        self._require_recent_mfa(mfa_verified_at)
        if not idempotency_key or len(idempotency_key) > 80:
            raise ValueError("a valid idempotency key is required")

        order = self._order(tenant_id, order_id)
        if order.cancel_idempotency_key is not None:
            if order.cancel_idempotency_key != idempotency_key:
                raise IdempotencyConflictError("order cancellation already requested")
            return self._view(order)
        duplicate = self.session.scalar(
            select(TradingOrder.id).where(
                TradingOrder.tenant_id == tenant_id,
                TradingOrder.cancel_idempotency_key == idempotency_key,
            )
        )
        if duplicate is not None:
            raise IdempotencyConflictError("cancel idempotency key already used")
        if order.status in {OrderStatus.FILLED, OrderStatus.REJECTED}:
            raise TradingGuardError("order can no longer be cancelled")

        account = self._account(tenant_id, order.account_id)
        credentials = self._credentials(account)
        order.cancel_idempotency_key = idempotency_key
        order.status = OrderStatus.CANCEL_PENDING
        self._publish_order(order, "trading.order.cancellation_requested")
        self.session.commit()

        try:
            result = self.connector.cancel_order(
                scope=order.account_scope,
                symbol=order.symbol,
                client_order_id=order.client_order_id,
                credentials=credentials,
            )
        except BinanceWriteTimeout as error:
            order.status = OrderStatus.UNKNOWN
            order.error_code = error.code
        except BinanceConnectorError as error:
            order.status = OrderStatus.UNKNOWN
            order.error_code = error.code
        else:
            order.status = result.status
            order.filled_quantity = result.filled_quantity
            order.average_price = result.average_price
            order.error_code = None
        self._publish_order(order, "trading.order.status_changed")
        self.session.commit()
        return self._view(order)

    def activate_kill_switch(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        reason: str,
        scope: str = "global",
    ) -> KillSwitch:
        switch = self.session.scalar(
            select(KillSwitch).where(
                KillSwitch.tenant_id == tenant_id,
                KillSwitch.scope == scope,
            )
        )
        if switch is None:
            switch = KillSwitch(
                tenant_id=tenant_id,
                scope=scope,
                active=True,
                reason=reason,
                activated_by=actor_user_id,
            )
            self.session.add(switch)
        else:
            switch.active = True
            switch.reason = reason
            switch.activated_by = actor_user_id
            switch.released_at = None
        self.session.flush()
        self.outbox.publish(
            tenant_id=tenant_id,
            event_type="trading.kill_switch.activated",
            aggregate_type="kill_switch",
            aggregate_id=switch.id,
            payload={"scope": switch.scope, "active": True},
        )
        self.session.commit()
        return switch

    def release_kill_switch(
        self,
        *,
        tenant_id: str,
        switch_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
    ) -> KillSwitch:
        if "tenant_admin" not in actor_roles:
            raise PermissionError("tenant administrator role is required")
        self._require_recent_mfa(mfa_verified_at)
        switch = self.session.scalar(
            select(KillSwitch).where(
                KillSwitch.id == switch_id,
                KillSwitch.tenant_id == tenant_id,
            )
        )
        if switch is None:
            raise LookupError("trading kill switch not found")
        switch.active = False
        switch.released_at = utc_now()
        self.outbox.publish(
            tenant_id=tenant_id,
            event_type="trading.kill_switch.released",
            aggregate_type="kill_switch",
            aggregate_id=switch.id,
            payload={"scope": switch.scope, "active": False},
        )
        self.session.commit()
        return switch

    def list_for_tenant(self, tenant_id: str) -> list[OrderView]:
        records = self.session.scalars(
            select(TradingOrder)
            .where(TradingOrder.tenant_id == tenant_id)
            .order_by(TradingOrder.created_at.desc())
        )
        return [self._view(record) for record in records]

    def _account(self, tenant_id: str, account_id: str) -> TradingAccount:
        account = self.session.scalar(
            select(TradingAccount).where(
                TradingAccount.id == account_id,
                TradingAccount.tenant_id == tenant_id,
            )
        )
        if account is None:
            raise LookupError("trading account not found")
        return account

    def _order(self, tenant_id: str, order_id: str) -> TradingOrder:
        order = self.session.scalar(
            select(TradingOrder).where(
                TradingOrder.id == order_id,
                TradingOrder.tenant_id == tenant_id,
            )
        )
        if order is None:
            raise LookupError("trading order not found")
        return order

    @staticmethod
    def _validate_account(account: TradingAccount) -> None:
        if (
            account.status is not AccountStatus.ACTIVE
            or not account.trading_enabled
            or account.can_withdraw
        ):
            raise TradingGuardError("trading account is not enabled")

    def _validate_scope(
        self,
        tenant_id: str,
        account_id: str,
        command: OrderCommand,
    ) -> None:
        scope_key = (
            command.symbol
            if command.account_scope is AccountScopeType.ISOLATED_MARGIN
            else "global"
        )
        scope = self.session.scalar(
            select(TradingAccountScope).where(
                TradingAccountScope.tenant_id == tenant_id,
                TradingAccountScope.account_id == account_id,
                TradingAccountScope.scope_type == command.account_scope,
                TradingAccountScope.scope_key == scope_key,
                TradingAccountScope.enabled.is_(True),
            )
        )
        if scope is None:
            raise TradingGuardError("account scope is not enabled")

    def _ensure_kill_switch_inactive(self, tenant_id: str, account_id: str) -> None:
        switch = self.session.scalar(
            select(KillSwitch).where(
                KillSwitch.tenant_id == tenant_id,
                KillSwitch.scope.in_(["global", f"account:{account_id}"]),
                KillSwitch.active.is_(True),
            )
        )
        if switch is not None:
            raise TradingGuardError("trading kill switch is active")

    def _credentials(self, account: TradingAccount) -> BinanceCredentials:
        if account.secret_ref is None or account.credential_type is None:
            raise TradingGuardError("account credentials are unavailable")
        values = self.secret_backend.get(account.secret_ref)
        return BinanceCredentials(
            api_key=values["api_key"],
            private_key_or_secret=values["private_key_or_secret"],
            credential_type=CredentialType(account.credential_type),
        )

    @staticmethod
    def _fingerprint(command: OrderCommand) -> str:
        payload = json.dumps(
            command.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _publish_order(self, order: TradingOrder, event_type: str) -> None:
        self.outbox.publish(
            tenant_id=order.tenant_id,
            event_type=event_type,
            aggregate_type="order",
            aggregate_id=order.id,
            payload={
                "order_id": order.id,
                "account_id": order.account_id,
                "client_order_id": order.client_order_id,
                "account_scope": order.account_scope.value,
                "symbol": order.symbol,
                "status": order.status.value,
                "error_code": order.error_code,
            },
        )

    @staticmethod
    def _require_trader(actor_roles: tuple[str, ...]) -> None:
        if not {"tenant_admin", "trader"}.intersection(actor_roles):
            raise PermissionError("trader role is required")

    @staticmethod
    def _require_recent_mfa(verified_at: datetime | None) -> None:
        if verified_at is None:
            raise PermissionError("recent MFA verification is required")
        normalized = verified_at if verified_at.tzinfo else verified_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - normalized > timedelta(minutes=5):
            raise PermissionError("recent MFA verification is required")

    @staticmethod
    def _view(order: TradingOrder) -> OrderView:
        return OrderView(
            id=order.id,
            tenant_id=order.tenant_id,
            account_id=order.account_id,
            client_order_id=order.client_order_id,
            broker_order_id=order.broker_order_id,
            account_scope=order.account_scope,
            symbol=order.symbol,
            side=OrderSide(order.side),
            position_side=PositionSide(order.position_side) if order.position_side else None,
            order_type=OrderType(order.order_type),
            quantity=order.quantity,
            limit_price=order.limit_price,
            reduce_only=order.reduce_only,
            margin_side_effect=MarginSideEffect(order.margin_side_effect),
            filled_quantity=order.filled_quantity,
            average_price=order.average_price,
            status=order.status,
            source=OrderSource(order.source),
            error_code=order.error_code,
            submitted_at=order.submitted_at,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
