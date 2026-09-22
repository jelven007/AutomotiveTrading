from __future__ import annotations

import os

import httpx
import pytest

RUN_DEMO_TESTS = os.getenv("RUN_BINANCE_DEMO_TESTS") == "true"
REQUIRED_ENV = (
    "BINANCE_DEMO_API_KEY",
    "BINANCE_DEMO_API_SECRET",
    "BINANCE_UAT_BASE_URL",
    "BINANCE_UAT_BEARER_TOKEN",
)
MISSING_ENV = tuple(name for name in REQUIRED_ENV if not os.getenv(name))

pytestmark = pytest.mark.skipif(
    not RUN_DEMO_TESTS or bool(MISSING_ENV),
    reason="未显式启用并提供 B Demo 验收凭据",
)


def test_demo_overview_and_write_gate() -> None:
    base_url = os.environ["BINANCE_UAT_BASE_URL"].rstrip("/")
    api_key = os.environ["BINANCE_DEMO_API_KEY"]
    api_secret = os.environ["BINANCE_DEMO_API_SECRET"]
    headers = {"Authorization": f"Bearer {os.environ['BINANCE_UAT_BEARER_TOKEN']}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=60) as client:
        bound = client.put(
            "/api/v1/trading/binance/account",
            json={
                "alias": os.getenv("BINANCE_UAT_ACCOUNT_ALIAS", "B 模拟验收"),
                "api_key": api_key,
                "api_secret": api_secret,
            },
        )
        assert bound.status_code == 200, _safe_failure(bound)
        assert bound.json()["environment"] == "demo"

        overview = client.get(
            "/api/v1/trading/binance/overview",
            params={"refresh": "true"},
        )
        assert overview.status_code == 200, _safe_failure(overview)
        payload = overview.json()

        assert payload["permissions"]["status"] == "ok"
        assert payload["permissions"]["data"]["can_read"] is True
        assert payload["permissions"]["data"]["ip_restricted"] is False
        assert payload["permissions"]["data"]["can_withdraw"] is False
        assert payload["permissions"]["data"]["can_internal_transfer"] is False
        assert payload["permissions"]["data"]["can_universal_transfer"] is False
        assert payload["spot"]["status"] == "ok"
        assert payload["usdm"]["status"] == "ok"

        # 下单接口交付前允许路由不存在, 交付后必须由 Demo 写入门禁拒绝。
        write_attempt = client.post(
            "/api/v1/trading/orders",
            headers={
                "Idempotency-Key": "demo-write-gate-probe",
            },
            json={
                "account_id": "demo-write-gate-probe",
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
                "trading.demo_disabled",
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
