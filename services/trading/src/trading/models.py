from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
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
    BINANCE = "binance"


class TradingProvider(StrEnum):
    BINANCE = "binance"


class CredentialType(StrEnum):
    HMAC = "hmac"


class AccountStatus(StrEnum):
    READ_ONLY = "read_only"


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "account_slot",
            name="uq_trading_accounts_provider_slot",
        ),
        CheckConstraint(
            "provider = 'binance' AND account_slot = 'primary'",
            name="ck_trading_accounts_binance_slot",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    market_group: Mapped[MarketGroup] = mapped_column(
        Enum(MarketGroup, native_enum=False, values_callable=enum_values)
    )
    provider: Mapped[TradingProvider] = mapped_column(
        Enum(TradingProvider, native_enum=False, values_callable=enum_values)
    )
    account_slot: Mapped[str] = mapped_column(String(24), default="primary")
    environment: Mapped[str] = mapped_column(String(24), default="demo")
    external_account_ref: Mapped[str | None] = mapped_column(String(160))
    credential_type: Mapped[CredentialType] = mapped_column(
        Enum(CredentialType, native_enum=False, values_callable=enum_values),
        default=CredentialType.HMAC,
    )
    api_key_fingerprint: Mapped[str | None] = mapped_column(String(80))
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_version: Mapped[int | None] = mapped_column(Integer)
    credential_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    credential_confirmed_by: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, values_callable=enum_values),
        default=AccountStatus.READ_ONLY,
    )
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False, values_callable=enum_values),
        default=ConnectionStatus.DISCONNECTED,
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
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class LocalEncryptedSecret(Base):
    __tablename__ = "local_encrypted_secrets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


__all__ = [
    "AccountStatus",
    "Base",
    "ConnectionStatus",
    "CredentialType",
    "LocalEncryptedSecret",
    "MarketGroup",
    "TradingAccount",
    "TradingProvider",
    "utc_now",
]
