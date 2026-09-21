from collections.abc import Callable, Mapping
from hashlib import sha256
from time import time
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionSnapshot
from trading.binance.signing import BinanceSigner

PERMISSION_PATH = "/sapi/v1/account/apiRestrictions"
OFFICIAL_HOSTS = frozenset({"api.binance.com", "testnet.binance.vision"})
ERROR_CODES = {
    -1021: ("binance.clock_skew", "Binance rejected the request timestamp"),
    -1022: ("binance.signature_invalid", "Binance rejected the request signature"),
    -2015: ("binance.credentials_invalid", "Binance API credentials or permissions are invalid"),
}


class BinancePermissionProbe:
    def __init__(
        self,
        *,
        http: httpx.Client,
        base_url: str = "https://api.binance.com",
        recv_window_ms: int = 5_000,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._validate_base_url(base_url)
        if not 1 <= recv_window_ms <= 5_000:
            raise ValueError("recvWindow must be between 1 and 5000 milliseconds")
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._recv_window_ms = recv_window_ms
        self._clock_ms = clock_ms or (lambda: int(time() * 1000))

    def inspect(
        self,
        *,
        api_key: str,
        api_secret: str,
    ) -> AccountPermissionSnapshot:
        payload = self._fetch_permissions(api_key, api_secret)
        permissions = self._map_permissions(api_key, payload)
        self._validate_permissions(permissions)
        return permissions

    def _fetch_permissions(
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
                f"{self._base_url}{PERMISSION_PATH}",
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
        expiration_time_ms = cls._required_non_negative_integer(
            payload,
            "tradingAuthorityExpirationTime",
        )
        return AccountPermissionSnapshot(
            external_account_ref=f"key-{sha256(api_key.encode()).hexdigest()[:16]}",
            ip_restricted=cls._required_boolean(payload, "ipRestrict"),
            can_read=cls._required_boolean(payload, "enableReading"),
            can_spot_trade=cls._required_boolean(
                payload,
                "enableSpotAndMarginTrading",
            ),
            can_margin_trade=cls._required_boolean(payload, "enableMargin"),
            can_futures_trade=cls._required_boolean(payload, "enableFutures"),
            can_withdraw=cls._required_boolean(payload, "enableWithdrawals"),
            can_internal_transfer=cls._required_boolean(
                payload,
                "enableInternalTransfer",
            ),
            can_universal_transfer=cls._required_boolean(
                payload,
                "permitsUniversalTransfer",
            ),
            trading_authority_expiration_time_ms=expiration_time_ms or None,
        )

    @staticmethod
    def _validate_permissions(permissions: AccountPermissionSnapshot) -> None:
        if not permissions.can_read:
            raise BinanceConnectorError(
                "binance.read_permission_required",
                "Binance account read permission is required",
            )
        if not permissions.ip_restricted:
            raise BinanceConnectorError(
                "binance.ip_not_allowed",
                "Binance API key must restrict access to the fixed egress IP",
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
    def _required_non_negative_integer(payload: Mapping[str, Any], field: str) -> int:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
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

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in OFFICIAL_HOSTS
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("only official Binance HTTPS hosts are allowed")


__all__ = ["BinancePermissionProbe"]
