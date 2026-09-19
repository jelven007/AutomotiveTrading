from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from time import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlparse

import httpx

from trading.accounts import AccountPermissionSnapshot
from trading.binance.errors import BinanceConnectorError, BinanceWriteTimeout
from trading.binance.signing import BinanceSigner
from trading.models import AccountScopeType, CredentialType, OrderStatus

if TYPE_CHECKING:
    from trading.orders import (
        MarginSideEffect,
        OrderExecutionResult,
        OrderSide,
        OrderType,
        PositionSide,
    )

OFFICIAL_HOSTS = frozenset({"api.binance.com", "fapi.binance.com"})
ERROR_CODES = {
    -1021: ("binance.clock_skew", "Binance rejected the request timestamp"),
    -1022: ("binance.signature_invalid", "Binance rejected the request signature"),
    -2015: ("binance.credentials_invalid", "Binance API credentials or permissions are invalid"),
}
ORDER_STATUS_MAP = {
    "NEW": OrderStatus.SUBMITTED,
    "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
    "FILLED": OrderStatus.FILLED,
    "CANCELED": OrderStatus.CANCELLED,
    "REJECTED": OrderStatus.REJECTED,
    "EXPIRED": OrderStatus.REJECTED,
    "EXPIRED_IN_MATCH": OrderStatus.REJECTED,
}
MARGIN_SIDE_EFFECTS = {
    "none": "NO_SIDE_EFFECT",
    "borrow": "MARGIN_BUY",
    "repay": "AUTO_REPAY",
    "auto_borrow_repay": "AUTO_BORROW_REPAY",
}


@dataclass(frozen=True, repr=False)
class BinanceCredentials:
    api_key: str
    private_key_or_secret: str
    credential_type: CredentialType

    def __repr__(self) -> str:
        return f"BinanceCredentials(credential_type={self.credential_type.value!r})"


class BinanceClient:
    def __init__(
        self,
        *,
        http: httpx.Client,
        spot_base_url: str = "https://api.binance.com",
        futures_base_url: str = "https://fapi.binance.com",
        recv_window_ms: int = 5_000,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._validate_base_url(spot_base_url)
        self._validate_base_url(futures_base_url)
        if not 1 <= recv_window_ms <= 5_000:
            raise ValueError("recvWindow must be between 1 and 5000 milliseconds")
        self.http = http
        self.spot_base_url = spot_base_url.rstrip("/")
        self.futures_base_url = futures_base_url.rstrip("/")
        self.recv_window_ms = recv_window_ms
        self.clock_ms = clock_ms or (lambda: int(time() * 1000))
        self._time_offsets: dict[str, int] = {}

    def inspect(
        self,
        *,
        credential_type: CredentialType,
        api_key: str,
        private_key_or_secret: str,
        scopes: tuple[AccountScopeType, ...],
        isolated_symbols: tuple[str, ...],
    ) -> AccountPermissionSnapshot:
        credentials = BinanceCredentials(
            api_key=api_key,
            private_key_or_secret=private_key_or_secret,
            credential_type=credential_type,
        )
        spot = self.signed_request("GET", "/api/v3/account", credentials)
        requested = set(scopes)

        margin_checks: list[bool] = []
        if AccountScopeType.CROSS_MARGIN in requested:
            cross = self.signed_request(
                "GET",
                "/sapi/v1/margin/account",
                credentials,
            )
            margin_checks.append(bool(cross.get("tradeEnabled")))
        if AccountScopeType.ISOLATED_MARGIN in requested:
            isolated = self.signed_request(
                "GET",
                "/sapi/v1/margin/isolated/account",
                credentials,
                params={"symbols": ",".join(isolated_symbols)},
            )
            assets = isolated.get("assets", [])
            margin_checks.append(
                isinstance(assets, list)
                and bool(assets)
                and all(bool(asset.get("enabled", True)) for asset in assets)
            )

        futures: dict[str, Any] = {}
        if AccountScopeType.USDM_FUTURES in requested:
            futures = self.signed_request(
                "GET",
                "/fapi/v3/account",
                credentials,
            )

        fallback_ref = f"key-{sha256(api_key.encode()).hexdigest()[:16]}"
        return AccountPermissionSnapshot(
            external_account_ref=str(spot.get("uid") or fallback_ref),
            can_read=True,
            can_spot_trade=bool(spot.get("canTrade")),
            can_margin_trade=all(margin_checks) if margin_checks else False,
            can_futures_trade=bool(futures.get("canTrade")),
            can_withdraw=bool(spot.get("canWithdraw")) or bool(futures.get("canWithdraw")),
        )

    def submit_order(
        self,
        *,
        scope: AccountScopeType,
        symbol: str,
        side: "OrderSide",
        order_type: "OrderType",
        quantity: str,
        limit_price: str | None,
        time_in_force: str | None,
        position_side: "PositionSide | None",
        reduce_only: bool,
        margin_side_effect: "MarginSideEffect",
        client_order_id: str,
        credentials: BinanceCredentials,
    ) -> "OrderExecutionResult":
        from trading.orders import OrderExecutionResult

        path = self._order_path(scope)
        params: dict[str, str | int | bool] = {
            "symbol": symbol,
            "side": side.value.upper(),
            "type": order_type.value.upper(),
            "quantity": quantity,
            "newClientOrderId": client_order_id,
        }
        if limit_price is not None:
            params["price"] = limit_price
        if time_in_force is not None:
            params["timeInForce"] = time_in_force
        if scope in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            params["isIsolated"] = "TRUE" if scope is AccountScopeType.ISOLATED_MARGIN else "FALSE"
            params["sideEffectType"] = MARGIN_SIDE_EFFECTS[margin_side_effect.value]
        if scope is AccountScopeType.USDM_FUTURES:
            if position_side is not None:
                params["positionSide"] = position_side.value.upper()
            params["reduceOnly"] = reduce_only

        payload = self.signed_request("POST", path, credentials, params=params)
        broker_order_id = payload.get("orderId")
        if broker_order_id is None:
            raise BinanceConnectorError(
                "binance.response_invalid",
                "Binance order response is missing orderId",
            )
        return OrderExecutionResult(
            broker_order_id=str(broker_order_id),
            status=ORDER_STATUS_MAP.get(
                str(payload.get("status")),
                OrderStatus.UNKNOWN,
            ),
            filled_quantity=str(payload.get("executedQty", "0")),
            average_price=(
                str(payload["avgPrice"]) if payload.get("avgPrice") not in {None, "0"} else None
            ),
        )

    def query_order(
        self,
        *,
        scope: AccountScopeType,
        symbol: str,
        client_order_id: str,
        credentials: BinanceCredentials,
    ) -> "OrderExecutionResult":
        from trading.orders import OrderExecutionResult

        params: dict[str, str | int | bool] = {
            "symbol": symbol,
            "origClientOrderId": client_order_id,
        }
        if scope in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            params["isIsolated"] = "TRUE" if scope is AccountScopeType.ISOLATED_MARGIN else "FALSE"
        payload = self.signed_request(
            "GET",
            self._order_path(scope),
            credentials,
            params=params,
        )
        return OrderExecutionResult(
            broker_order_id=str(payload.get("orderId", "")),
            status=ORDER_STATUS_MAP.get(
                str(payload.get("status")),
                OrderStatus.UNKNOWN,
            ),
            filled_quantity=str(payload.get("executedQty", "0")),
            average_price=(
                str(payload["avgPrice"]) if payload.get("avgPrice") not in {None, "0"} else None
            ),
        )

    def cancel_order(
        self,
        *,
        scope: AccountScopeType,
        symbol: str,
        client_order_id: str,
        credentials: BinanceCredentials,
    ) -> "OrderExecutionResult":
        from trading.orders import OrderExecutionResult

        params: dict[str, str | int | bool] = {
            "symbol": symbol,
            "origClientOrderId": client_order_id,
        }
        if scope in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            params["isIsolated"] = "TRUE" if scope is AccountScopeType.ISOLATED_MARGIN else "FALSE"
        payload = self.signed_request(
            "DELETE",
            self._order_path(scope),
            credentials,
            params=params,
        )
        return OrderExecutionResult(
            broker_order_id=str(payload.get("orderId", "")),
            status=ORDER_STATUS_MAP.get(
                str(payload.get("status")),
                OrderStatus.CANCELLED,
            ),
            filled_quantity=str(payload.get("executedQty", "0")),
        )

    def margin_borrow_repay(
        self,
        *,
        scope: AccountScopeType,
        asset: str,
        amount: str,
        action: str,
        credentials: BinanceCredentials,
        isolated_symbol: str | None = None,
    ) -> str:
        if scope not in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            raise ValueError("borrow and repay require a margin scope")
        if action not in {"BORROW", "REPAY"}:
            raise ValueError("margin action must be BORROW or REPAY")
        params: dict[str, str | int | bool] = {
            "asset": asset.upper(),
            "amount": amount,
            "type": action,
            "isIsolated": scope is AccountScopeType.ISOLATED_MARGIN,
        }
        if scope is AccountScopeType.ISOLATED_MARGIN:
            if not isolated_symbol:
                raise ValueError("isolated margin requires a symbol")
            params["symbol"] = isolated_symbol.upper()
        payload = self.signed_request(
            "POST",
            "/sapi/v1/margin/borrow-repay",
            credentials,
            params=params,
        )
        return str(payload["tranId"])

    def account_snapshot(
        self,
        *,
        scope: AccountScopeType,
        credentials: BinanceCredentials,
        isolated_symbols: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        paths = {
            AccountScopeType.SPOT: "/api/v3/account",
            AccountScopeType.CROSS_MARGIN: "/sapi/v1/margin/account",
            AccountScopeType.ISOLATED_MARGIN: "/sapi/v1/margin/isolated/account",
            AccountScopeType.USDM_FUTURES: "/fapi/v3/account",
        }
        params: dict[str, str] = {}
        if scope is AccountScopeType.ISOLATED_MARGIN:
            if not isolated_symbols:
                raise ValueError("isolated margin snapshot requires symbols")
            params["symbols"] = ",".join(symbol.upper() for symbol in isolated_symbols)
        return self.signed_request(
            "GET",
            paths[scope],
            credentials,
            params=params,
        )

    def set_futures_leverage(
        self,
        *,
        symbol: str,
        leverage: int,
        credentials: BinanceCredentials,
    ) -> dict[str, Any]:
        if not 1 <= leverage <= 125:
            raise ValueError("futures leverage must be between 1 and 125")
        return self.signed_request(
            "POST",
            "/fapi/v1/leverage",
            credentials,
            params={"symbol": symbol.upper(), "leverage": leverage},
        )

    def signed_request(
        self,
        method: str,
        path: str,
        credentials: BinanceCredentials,
        *,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, Any]:
        base_url = self._base_url(path)
        if base_url not in self._time_offsets:
            self._synchronize_time(base_url)

        signed_params = {key: self._parameter_value(value) for key, value in (params or {}).items()}
        signed_params["recvWindow"] = str(self.recv_window_ms)
        signed_params["timestamp"] = str(self.clock_ms() + self._time_offsets[base_url])
        payload = urlencode(list(signed_params.items()))
        signed_params["signature"] = BinanceSigner.sign(
            credentials.credential_type,
            credentials.private_key_or_secret,
            payload,
        )
        try:
            response = self.http.request(
                method,
                f"{base_url}{path}",
                headers={"X-MBX-APIKEY": credentials.api_key},
                params=signed_params,
                timeout=5,
            )
        except httpx.TimeoutException as error:
            if method.upper() in {"POST", "PUT", "DELETE"}:
                raise BinanceWriteTimeout() from error
            raise BinanceConnectorError(
                "binance.timeout",
                "Binance request timed out",
            ) from error
        return self._response_json(response)

    def _synchronize_time(self, base_url: str) -> None:
        path = "/fapi/v1/time" if base_url == self.futures_base_url else "/api/v3/time"
        try:
            response = self.http.get(f"{base_url}{path}", timeout=3)
        except httpx.TimeoutException as error:
            raise BinanceConnectorError(
                "binance.time_unavailable",
                "Binance server time is unavailable",
            ) from error
        payload = self._response_json(response)
        server_time = payload.get("serverTime")
        if not isinstance(server_time, int):
            raise BinanceConnectorError(
                "binance.response_invalid",
                "Binance server time response is invalid",
            )
        self._time_offsets[base_url] = server_time - self.clock_ms()

    def _base_url(self, path: str) -> str:
        return self.futures_base_url if path.startswith("/fapi/") else self.spot_base_url

    @staticmethod
    def _order_path(scope: AccountScopeType) -> str:
        if scope is AccountScopeType.SPOT:
            return "/api/v3/order"
        if scope in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            return "/sapi/v1/margin/order"
        return "/fapi/v1/order"

    @staticmethod
    def _parameter_value(value: str | int | bool) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

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
