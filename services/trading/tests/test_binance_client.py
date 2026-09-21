from collections.abc import Callable

import httpx
import pytest
from trading.binance.client import BinancePermissionProbe
from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionSnapshot


def permission_payload(**overrides: bool | int) -> dict[str, bool | int]:
    payload: dict[str, bool | int] = {
        "ipRestrict": True,
        "enableReading": True,
        "enableSpotAndMarginTrading": True,
        "enableMargin": False,
        "enableFutures": True,
        "enableWithdrawals": False,
        "enableInternalTransfer": False,
        "permitsUniversalTransfer": False,
        "tradingAuthorityExpirationTime": 0,
    }
    payload.update(overrides)
    return payload


def probe(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[BinancePermissionProbe, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(record))
    return BinancePermissionProbe(http=http, clock_ms=lambda: 1_700_000_000_000), requests


def inspect(client: BinancePermissionProbe) -> AccountPermissionSnapshot:
    return client.inspect(
        api_key="production-api-key",
        api_secret="hmac-secret",
    )


def test_permission_probe_only_calls_the_restrictions_endpoint() -> None:
    client, requests = probe(lambda _: httpx.Response(200, json=permission_payload()))

    result = inspect(client)

    assert result == AccountPermissionSnapshot(
        external_account_ref="key-784c2e8dfba5a7ff",
        ip_restricted=True,
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
        ("GET", "/sapi/v1/account/apiRestrictions")
    ]
    assert requests[0].headers["X-MBX-APIKEY"] == "production-api-key"
    assert "hmac-secret" not in str(requests[0].url)
    assert not hasattr(client, "signed_request")
    assert not hasattr(client, "submit_order")
    assert not hasattr(client, "cancel_order")


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"enableReading": False}, "binance.read_permission_required"),
        ({"ipRestrict": False}, "binance.ip_not_allowed"),
        ({"enableWithdrawals": True}, "binance.unsafe_permissions"),
        ({"enableInternalTransfer": True}, "binance.unsafe_permissions"),
        ({"permitsUniversalTransfer": True}, "binance.unsafe_permissions"),
    ],
)
def test_permission_probe_rejects_unsafe_permissions(
    overrides: dict[str, bool],
    expected_code: str,
) -> None:
    client, _ = probe(lambda _: httpx.Response(200, json=permission_payload(**overrides)))

    with pytest.raises(BinanceConnectorError) as error:
        inspect(client)

    assert error.value.code == expected_code


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
def test_permission_probe_maps_binance_errors(
    status_code: int,
    payload: dict[str, int],
    expected_code: str,
) -> None:
    client, _ = probe(lambda _: httpx.Response(status_code, json=payload))

    with pytest.raises(BinanceConnectorError) as error:
        inspect(client)

    assert error.value.code == expected_code
    assert "hmac-secret" not in str(error.value)


def test_permission_probe_rejects_non_official_host() -> None:
    with pytest.raises(ValueError, match="official Binance HTTPS hosts"):
        BinancePermissionProbe(
            http=httpx.Client(),
            base_url="https://attacker.example",
        )
