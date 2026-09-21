from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AccountPermissionSnapshot:
    external_account_ref: str
    ip_restricted: bool
    can_read: bool
    can_spot_trade: bool
    can_margin_trade: bool
    can_futures_trade: bool
    can_withdraw: bool
    can_internal_transfer: bool
    can_universal_transfer: bool
    trading_authority_expiration_time_ms: int | None = None


class AccountPermissionProbe(Protocol):
    def inspect(
        self,
        *,
        api_key: str,
        api_secret: str,
    ) -> AccountPermissionSnapshot: ...


__all__ = ["AccountPermissionProbe", "AccountPermissionSnapshot"]
