from __future__ import annotations

import os

import httpx
import pytest

RUN_PRODUCTION_TESTS = os.getenv("RUN_BINANCE_PRODUCTION_READ_ONLY_TESTS") == "true"
REQUIRED_ENV = (
    "BINANCE_PRODUCTION_API_KEY",
    "BINANCE_PRODUCTION_API_SECRET",
    "BINANCE_UAT_BASE_URL",
    "BINANCE_UAT_BEARER_TOKEN",
)
MISSING_ENV = tuple(name for name in REQUIRED_ENV if not os.getenv(name))

pytestmark = pytest.mark.skipif(
    not RUN_PRODUCTION_TESTS or bool(MISSING_ENV),
    reason="未显式启用并提供币安生产只读验收凭据",
)


def test_production_read_only_overview() -> None:
    base_url = os.environ["BINANCE_UAT_BASE_URL"].rstrip("/")
    api_key = os.environ["BINANCE_PRODUCTION_API_KEY"]
    api_secret = os.environ["BINANCE_PRODUCTION_API_SECRET"]
    headers = {"Authorization": f"Bearer {os.environ['BINANCE_UAT_BEARER_TOKEN']}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=60) as client:
        bound = client.put(
            "/api/v1/trading/binance/account",
            json={
                "alias": os.getenv("BINANCE_UAT_ACCOUNT_ALIAS", "生产只读验收"),
                "api_key": api_key,
                "api_secret": api_secret,
                "ip_whitelist_confirmed": True,
            },
        )
        assert bound.status_code == 200, _safe_failure(bound)

        overview = client.get(
            "/api/v1/trading/binance/overview",
            params={"refresh": "true"},
        )
        assert overview.status_code == 200, _safe_failure(overview)
        payload = overview.json()

        assert payload["permissions"]["status"] == "ok"
        assert payload["permissions"]["data"]["can_read"] is True
        assert payload["permissions"]["data"]["ip_restricted"] is True
        assert payload["permissions"]["data"]["can_withdraw"] is False
        assert payload["permissions"]["data"]["can_internal_transfer"] is False
        assert payload["permissions"]["data"]["can_universal_transfer"] is False
        assert payload["spot"]["status"] == "ok"
        assert payload["usdm"]["status"] == "ok"

        # 阶段一允许路由不存在, 也允许统一返回写功能关闭。
        write_attempt = client.post(
            "/api/v1/trading/orders",
            headers={
                "Idempotency-Key": "production-readonly-probe",
            },
            json={
                "account_id": "production-readonly-probe",
                "account_scope": "spot",
                "symbol": "BTCUSDT",
                "side": "buy",
                "order_type": "market",
                "quantity": "0.00001",
            },
        )
        assert write_attempt.status_code in {404, 409}
        if write_attempt.status_code == 409:
            assert write_attempt.json()["code"] in {
                "trading.live_disabled",
                "binance.trading_disabled",
            }

        combined_response = f"{bound.text}\n{overview.text}\n{write_attempt.text}"
        assert api_key not in combined_response
        assert api_secret not in combined_response


def _safe_failure(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"status={response.status_code}"
    if isinstance(payload, dict):
        return f"status={response.status_code}, code={payload.get('code', 'unknown')}"
    return f"status={response.status_code}"
