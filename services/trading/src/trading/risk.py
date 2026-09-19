from typing import Any, Protocol


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
