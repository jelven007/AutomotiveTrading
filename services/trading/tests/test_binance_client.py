from collections.abc import Callable

import httpx
import pytest
from trading.accounts import AccountPermissionSnapshot
from trading.binance.client import BinanceClient, BinanceCredentials
from trading.binance.errors import BinanceConnectorError, BinanceWriteTimeout
from trading.models import AccountScopeType, CredentialType
from trading.orders import MarginSideEffect, OrderSide, OrderType, PositionSide


def mock_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[BinanceClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(recording_handler))
    client = BinanceClient(http=http, clock_ms=lambda: 1_700_000_000_000)
    return client, requests


def credentials() -> BinanceCredentials:
    return BinanceCredentials(
        api_key="production-api-key",
        private_key_or_secret="hmac-secret",
        credential_type=CredentialType.HMAC,
    )


def test_permission_probe_checks_spot_margin_and_futures_without_leaking_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        responses = {
            "/api/v3/time": {"serverTime": 1_700_000_000_100},
            "/fapi/v1/time": {"serverTime": 1_700_000_000_120},
            "/api/v3/account": {
                "uid": 42,
                "canTrade": True,
                "canWithdraw": False,
            },
            "/sapi/v1/margin/account": {"tradeEnabled": True},
            "/sapi/v1/margin/isolated/account": {
                "assets": [{"symbol": "BTCUSDT", "enabled": True}]
            },
            "/fapi/v3/account": {"canTrade": True, "canWithdraw": False},
        }
        return httpx.Response(200, json=responses[request.url.path])

    client, requests = mock_client(handler)

    result = client.inspect(
        credential_type=CredentialType.HMAC,
        api_key="production-api-key",
        private_key_or_secret="hmac-secret",
        scopes=tuple(AccountScopeType),
        isolated_symbols=("BTCUSDT",),
    )

    assert result == AccountPermissionSnapshot(
        external_account_ref="42",
        can_read=True,
        can_spot_trade=True,
        can_margin_trade=True,
        can_futures_trade=True,
        can_withdraw=False,
    )
    paths = {request.url.path for request in requests}
    assert {
        "/api/v3/time",
        "/fapi/v1/time",
        "/api/v3/account",
        "/sapi/v1/margin/account",
        "/sapi/v1/margin/isolated/account",
        "/fapi/v3/account",
    } <= paths
    for request in requests:
        assert request.headers.get("X-MBX-APIKEY") in {None, "production-api-key"}
        assert "hmac-secret" not in str(request.url)
        if "signature" in request.url.params:
            assert int(request.url.params["recvWindow"]) <= 5_000


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_code"),
    [
        (429, {"code": -1003}, "binance.rate_limited"),
        (418, {"code": -1003}, "binance.ip_banned"),
        (400, {"code": -1021}, "binance.clock_skew"),
        (400, {"code": -1022}, "binance.signature_invalid"),
        (401, {"code": -2015}, "binance.credentials_invalid"),
    ],
)
def test_binance_errors_are_mapped_to_stable_codes(
    status_code: int,
    payload: dict[str, int],
    expected_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        return httpx.Response(status_code, json=payload)

    client, _ = mock_client(handler)

    with pytest.raises(BinanceConnectorError) as captured:
        client.signed_request(
            "GET",
            "/api/v3/account",
            credentials(),
        )

    assert captured.value.code == expected_code
    assert "hmac-secret" not in str(captured.value)


def test_non_official_binance_hosts_are_rejected() -> None:
    with pytest.raises(ValueError, match="official Binance HTTPS hosts"):
        BinanceClient(
            http=httpx.Client(),
            spot_base_url="https://attacker.example",
        )


@pytest.mark.parametrize(
    ("scope", "expected_path", "expected_parameters"),
    [
        (AccountScopeType.SPOT, "/api/v3/order", {}),
        (
            AccountScopeType.CROSS_MARGIN,
            "/sapi/v1/margin/order",
            {"isIsolated": "FALSE", "sideEffectType": "NO_SIDE_EFFECT"},
        ),
        (
            AccountScopeType.ISOLATED_MARGIN,
            "/sapi/v1/margin/order",
            {"isIsolated": "TRUE", "sideEffectType": "MARGIN_BUY"},
        ),
        (
            AccountScopeType.USDM_FUTURES,
            "/fapi/v1/order",
            {"positionSide": "BOTH", "reduceOnly": "false"},
        ),
    ],
)
def test_submit_order_maps_each_product_to_its_official_endpoint(
    scope: AccountScopeType,
    expected_path: str,
    expected_parameters: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/api/v3/time", "/fapi/v1/time"}:
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        return httpx.Response(
            200,
            json={"orderId": 12345, "status": "NEW", "executedQty": "0"},
        )

    client, requests = mock_client(handler)

    result = client.submit_order(
        scope=scope,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity="0.01",
        limit_price="50000",
        time_in_force="GTC",
        position_side=(PositionSide.BOTH if scope is AccountScopeType.USDM_FUTURES else None),
        reduce_only=False,
        margin_side_effect=(
            MarginSideEffect.BORROW
            if scope is AccountScopeType.ISOLATED_MARGIN
            else MarginSideEffect.NONE
        ),
        client_order_id="qt_test_order",
        credentials=credentials(),
    )

    order_request = requests[-1]
    assert order_request.url.path == expected_path
    assert result.broker_order_id == "12345"
    assert result.status == "submitted"
    assert order_request.url.params["newClientOrderId"] == "qt_test_order"
    for name, value in expected_parameters.items():
        assert order_request.url.params[name] == value


def test_submit_timeout_is_not_retried() -> None:
    order_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal order_attempts
        if request.url.path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        order_attempts += 1
        raise httpx.ReadTimeout("response lost", request=request)

    client, _ = mock_client(handler)

    with pytest.raises(BinanceWriteTimeout):
        client.submit_order(
            scope=AccountScopeType.SPOT,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity="0.01",
            limit_price=None,
            time_in_force=None,
            position_side=None,
            reduce_only=False,
            margin_side_effect=MarginSideEffect.NONE,
            client_order_id="qt_timeout",
            credentials=credentials(),
        )

    assert order_attempts == 1


@pytest.mark.parametrize(
    ("scope", "expected_path"),
    [
        (AccountScopeType.SPOT, "/api/v3/account"),
        (AccountScopeType.CROSS_MARGIN, "/sapi/v1/margin/account"),
        (
            AccountScopeType.ISOLATED_MARGIN,
            "/sapi/v1/margin/isolated/account",
        ),
        (AccountScopeType.USDM_FUTURES, "/fapi/v3/account"),
    ],
)
def test_account_snapshot_routes_balance_and_position_queries(
    scope: AccountScopeType,
    expected_path: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/api/v3/time", "/fapi/v1/time"}:
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        return httpx.Response(200, json={"snapshot": "ok"})

    client, requests = mock_client(handler)

    result = client.account_snapshot(
        scope=scope,
        credentials=credentials(),
        isolated_symbols=("BTCUSDT",),
    )

    assert result == {"snapshot": "ok"}
    assert requests[-1].url.path == expected_path
    if scope is AccountScopeType.ISOLATED_MARGIN:
        assert requests[-1].url.params["symbols"] == "BTCUSDT"


@pytest.mark.parametrize("action", ["BORROW", "REPAY"])
def test_margin_borrow_and_repay_use_dedicated_endpoint(action: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        return httpx.Response(200, json={"tranId": 987})

    client, requests = mock_client(handler)

    transaction_id = client.margin_borrow_repay(
        scope=AccountScopeType.ISOLATED_MARGIN,
        asset="USDT",
        amount="10",
        action=action,
        isolated_symbol="BTCUSDT",
        credentials=credentials(),
    )

    request = requests[-1]
    assert transaction_id == "987"
    assert request.url.path == "/sapi/v1/margin/borrow-repay"
    assert request.url.params["type"] == action
    assert request.url.params["isIsolated"] == "true"
    assert request.url.params["symbol"] == "BTCUSDT"


def test_futures_leverage_uses_usdm_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fapi/v1/time":
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        return httpx.Response(
            200,
            json={"symbol": "BTCUSDT", "leverage": 5, "maxNotionalValue": "100000"},
        )

    client, requests = mock_client(handler)

    result = client.set_futures_leverage(
        symbol="BTCUSDT",
        leverage=5,
        credentials=credentials(),
    )

    assert result["leverage"] == 5
    assert requests[-1].url.path == "/fapi/v1/leverage"
