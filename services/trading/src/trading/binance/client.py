from collections.abc import Callable, Mapping
from hashlib import sha256
from time import time
from typing import Any
from urllib.parse import urlencode

import httpx

from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionSnapshot
from trading.binance.signing import BinanceSigner

ACCOUNT_PATH = "/api/v3/account"
DEMO_BASE_URL = "https://demo-api.binance.com"
ERROR_CODES = {
    -1021: ("binance.clock_skew", "Binance rejected the request timestamp"),
    -1022: ("binance.signature_invalid", "Binance rejected the request signature"),
    -2015: ("binance.credentials_invalid", "Binance API credentials or permissions are invalid"),
}


class BinanceDemoAccountProbe:
    def __init__(
        self,
        *,
        http: httpx.Client,
        recv_window_ms: int = 5_000,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if not 1 <= recv_window_ms <= 5_000:
            raise ValueError("recvWindow must be between 1 and 5000 milliseconds")
        self._http = http
        self._recv_window_ms = recv_window_ms
        self._clock_ms = clock_ms or (lambda: int(time() * 1000))

    def inspect(
        self,
        *,
        api_key: str,
        api_secret: str,
    ) -> AccountPermissionSnapshot:
        payload = self._fetch_account(api_key, api_secret)
        permissions = self._map_permissions(api_key, payload)
        self._validate_permissions(permissions)
        return permissions

    def _fetch_account(
        self,
        api_key: str,
        api_secret: str,
    ) -> Mapping[str, Any]:
        params = {
            "recvWindow": str(self._recv_window_ms),
            "timestamp": str(self._clock_ms()),
        }
        query = urlencode(list(params.items()))
        params["signature"] = BinanceSigner.sign(api_secret, query)
        try:
            response = self._http.get(
                f"{DEMO_BASE_URL}{ACCOUNT_PATH}",
                headers={"X-MBX-APIKEY": api_key},
                params=params,
                timeout=5,
            )
        except httpx.TimeoutException as error:
            raise BinanceConnectorError(
                "binance.timeout",
                "Binance permission request timed out",
            ) from error
        return self._response_json(response)

    @classmethod
    def _map_permissions(
        cls,
        api_key: str,
        payload: Mapping[str, Any],
    ) -> AccountPermissionSnapshot:
        can_trade = cls._required_boolean(payload, "canTrade")
        uid = payload.get("uid")
        external_account_ref = (
            f"uid-{uid}"
            if isinstance(uid, int) and not isinstance(uid, bool) and uid >= 0
            else f"key-{sha256(api_key.encode()).hexdigest()[:16]}"
        )
        # Demo has no SAPI key-restrictions endpoint; unsupported
        # mainnet-only withdrawal and transfer capabilities remain disabled.
        return AccountPermissionSnapshot(
            external_account_ref=external_account_ref,
            ip_restricted=False,
            can_read=True,
            can_spot_trade=can_trade,
            can_margin_trade=False,
            can_futures_trade=can_trade,
            can_withdraw=False,
            can_internal_transfer=False,
            can_universal_transfer=False,
            trading_authority_expiration_time_ms=None,
        )

    @staticmethod
    def _validate_permissions(permissions: AccountPermissionSnapshot) -> None:
        if not permissions.can_read:
            raise BinanceConnectorError(
                "binance.read_permission_required",
                "Binance account read permission is required",
            )
        if (
            permissions.can_withdraw
            or permissions.can_internal_transfer
            or permissions.can_universal_transfer
        ):
            raise BinanceConnectorError(
                "binance.unsafe_permissions",
                "Binance withdrawal and transfer permissions must be disabled",
            )

    @staticmethod
    def _required_boolean(payload: Mapping[str, Any], field: str) -> bool:
        value = payload.get(field)
        if not isinstance(value, bool):
            raise BinanceConnectorError(
                "binance.response_invalid",
                f"Binance API key permissions are missing {field}",
            )
        return value

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise BinanceConnectorError(
                "binance.response_invalid",
                "Binance returned an invalid response",
                status_code=response.status_code,
            ) from error
        if response.is_success and isinstance(payload, dict):
            return payload

        exchange_code = payload.get("code") if isinstance(payload, dict) else None
        if response.status_code == 418:
            code, message = "binance.ip_banned", "Binance temporarily banned the client IP"
        elif response.status_code == 429:
            code, message = "binance.rate_limited", "Binance request limit exceeded"
        else:
            mapped_error = (
                ERROR_CODES.get(exchange_code) if isinstance(exchange_code, int) else None
            )
            code, message = mapped_error or (
                "binance.request_rejected",
                "Binance rejected the request",
            )
        retry_after = response.headers.get("Retry-After")
        raise BinanceConnectorError(
            code,
            message,
            status_code=response.status_code,
            retry_after_seconds=int(retry_after) if retry_after and retry_after.isdigit() else None,
        )


__all__ = ["BinanceDemoAccountProbe"]
