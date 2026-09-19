from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


class RiskAuthorizer(Protocol):
    def authorize(
        self,
        *,
        tenant_id: str,
        account_id: str,
        order: dict[str, Any],
        approval_token: str,
    ) -> bool: ...


class DenyAllRiskAuthorizer:
    def authorize(
        self,
        *,
        tenant_id: str,
        account_id: str,
        order: dict[str, Any],
        approval_token: str,
    ) -> bool:
        del tenant_id, account_id, order, approval_token
        return False


class HttpRiskAuthorizer:
    def __init__(self, http: httpx.Client, base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("risk service URL must use HTTPS")
        self._http = http
        self._base_url = base_url.rstrip("/")

    def authorize(
        self,
        *,
        tenant_id: str,
        account_id: str,
        order: dict[str, Any],
        approval_token: str,
    ) -> bool:
        if not approval_token:
            return False
        try:
            response = self._http.post(
                f"{self._base_url}/api/v1/risk/order-authorizations/verify",
                headers={"X-Risk-Approval": approval_token},
                json={
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "order": order,
                },
                timeout=3,
            )
        except httpx.HTTPError:
            return False
        if not response.is_success:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        return isinstance(payload, dict) and payload.get("approved") is True
