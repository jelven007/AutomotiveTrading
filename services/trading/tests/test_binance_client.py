from collections.abc import Callable

import httpx
import pytest
from trading.binance.client import BinanceDemoAccountProbe
from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionSnapshot


def account_payload(**overrides: bool | int) -> dict[str, bool | int]:
    payload: dict[str, bool | int] = {
        "canTrade": True,
        "canWithdraw": False,
        "uid": 42,
    }
    payload.update(overrides)
    return payload


def probe(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[BinanceDemoAccountProbe, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(record))
    return (
        BinanceDemoAccountProbe(http=http, clock_ms=lambda: 1_700_000_000_000),
        requests,
    )


def inspect(
    client: BinanceDemoAccountProbe,
) -> AccountPermissionSnapshot:
    return client.inspect(
        api_key="demo-api-key",
        api_secret="hmac-secret",
    )


def test_account_probe_only_calls_the_spot_demo_account_endpoint() -> None:
    client, requests = probe(lambda _: httpx.Response(200, json=account_payload()))

    result = inspect(client)

    assert result == AccountPermissionSnapshot(
        external_account_ref="uid-42",
        ip_restricted=False,
        can_read=True,
        can_spot_trade=True,
        can_margin_trade=False,
        can_futures_trade=True,
        can_withdraw=False,
        can_internal_transfer=False,
        can_universal_transfer=False,
        trading_authority_expiration_time_ms=None,
    )
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v3/account")
    ]
    assert requests[0].url.host == "demo-api.binance.com"
    assert requests[0].headers["X-MBX-APIKEY"] == "demo-api-key"
    assert "hmac-secret" not in str(requests[0].url)
    assert not hasattr(client, "signed_request")
    assert not hasattr(client, "submit_order")
    assert not hasattr(client, "cancel_order")


def test_account_probe_rejects_malformed_demo_response() -> None:
    client, _ = probe(lambda _: httpx.Response(200, json={"uid": 42}))

    with pytest.raises(BinanceConnectorError) as error:
        inspect(client)

    assert error.value.code == "binance.response_invalid"


def test_account_probe_reports_unreachable_demo_endpoint() -> None:
    def reject(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset", request=request)

    client, _ = probe(reject)

    with pytest.raises(BinanceConnectorError) as error:
        inspect(client)

    assert error.value.code == "binance.unreachable"
    assert error.value.status_code == 503
    assert "hmac-secret" not in str(error.value)


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
def test_account_probe_maps_binance_errors(
    status_code: int,
    payload: dict[str, int],
    expected_code: str,
) -> None:
    client, _ = probe(lambda _: httpx.Response(status_code, json=payload))

    with pytest.raises(BinanceConnectorError) as error:
        inspect(client)

    assert error.value.code == expected_code
    assert "hmac-secret" not in str(error.value)
