from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from trading.db import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_type]


class MarketGroup(StrEnum):
    CN_EQUITY = "cn_equity"
    HK_US_EQUITY = "hk_us_equity"
    BINANCE = "binance"


class TradingProvider(StrEnum):
    TONGHUASHUN = "tonghuashun"
    CAIXIN = "caixin"
    FUTU = "futu"
    LONGBRIDGE = "longbridge"
    BINANCE = "binance"


class CredentialType(StrEnum):
    ED25519 = "ed25519"
    HMAC = "hmac"
    RSA = "rsa"


class AccountScopeType(StrEnum):
    SPOT = "spot"
    CROSS_MARGIN = "cross_margin"
    ISOLATED_MARGIN = "isolated_margin"
    USDM_FUTURES = "usdm_futures"


class AccountStatus(StrEnum):
    PENDING_AUTHORIZATION = "pending_authorization"
    READ_ONLY = "read_only"
    ACTIVE = "active"
    DISABLED = "disabled"


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class OrderStatus(StrEnum):
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "alias"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    market_group: Mapped[MarketGroup] = mapped_column(
        Enum(MarketGroup, native_enum=False, values_callable=enum_values)
    )
    provider: Mapped[TradingProvider] = mapped_column(
        Enum(TradingProvider, native_enum=False, values_callable=enum_values)
    )
    environment: Mapped[str] = mapped_column(String(24), nullable=False)
    external_account_ref: Mapped[str | None] = mapped_column(String(160))
    credential_type: Mapped[CredentialType | None] = mapped_column(
        Enum(CredentialType, native_enum=False, values_callable=enum_values)
    )
    api_key_fingerprint: Mapped[str | None] = mapped_column(String(80))
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, values_callable=enum_values)
    )
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False, values_callable=enum_values)
    )
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_spot_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    can_margin_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    can_futures_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    can_withdraw: Mapped[bool] = mapped_column(Boolean, default=False)
    can_internal_transfer: Mapped[bool] = mapped_column(Boolean, default=True)
    can_universal_transfer: Mapped[bool] = mapped_column(Boolean, default=True)
    trading_authority_expiration_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    last_permission_check_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class TradingAccountScope(Base):
    __tablename__ = "trading_account_scopes"
    __table_args__ = (UniqueConstraint("tenant_id", "account_id", "scope_type", "scope_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("trading_accounts.id"), nullable=False, index=True
    )
    scope_type: Mapped[AccountScopeType] = mapped_column(
        Enum(AccountScopeType, native_enum=False, values_callable=enum_values)
    )
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    position_mode: Mapped[str | None] = mapped_column(String(24))
    margin_mode: Mapped[str | None] = mapped_column(String(24))
    leverage_limit: Mapped[int | None] = mapped_column(Integer)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class TradingOrder(Base):
    __tablename__ = "trading_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        UniqueConstraint("tenant_id", "cancel_idempotency_key"),
        UniqueConstraint("tenant_id", "account_id", "client_order_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("trading_accounts.id"), nullable=False, index=True
    )
    client_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(80))
    account_scope: Mapped[AccountScopeType] = mapped_column(
        Enum(AccountScopeType, native_enum=False, values_callable=enum_values)
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    position_side: Mapped[str | None] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    time_in_force: Mapped[str | None] = mapped_column(String(8))
    quantity: Mapped[str] = mapped_column(String(40), nullable=False)
    limit_price: Mapped[str | None] = mapped_column(String(40))
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False)
    margin_side_effect: Mapped[str] = mapped_column(String(32), default="none")
    filled_quantity: Mapped[str] = mapped_column(String(40), default="0")
    average_price: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, values_callable=enum_values)
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    cancel_idempotency_key: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(80))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class KillSwitch(Base):
    __tablename__ = "trading_kill_switches"
    __table_args__ = (UniqueConstraint("tenant_id", "scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    activated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)


class TradingOperation(Base):
    __tablename__ = "trading_operations"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("trading_accounts.id"), nullable=False, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    account_scope: Mapped[AccountScopeType] = mapped_column(
        Enum(AccountScopeType, native_enum=False, values_callable=enum_values)
    )
    symbol: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    broker_reference: Mapped[str | None] = mapped_column(String(120))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class LocalEncryptedSecret(Base):
    __tablename__ = "local_encrypted_secrets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)


__all__: list[Any] = [
    MarketGroup,
    TradingProvider,
    CredentialType,
    AccountScopeType,
    AccountStatus,
    ConnectionStatus,
    OrderStatus,
    TradingAccount,
    TradingAccountScope,
    TradingOrder,
    KillSwitch,
    TradingOperation,
    LocalEncryptedSecret,
    OutboxEvent,
]
