import json

import httpx
import pytest
from trading.risk import HttpRiskAuthorizer
from trading.secrets import HttpKmsSecretBackend, InMemoryEncryptedSecretBackend


def test_internal_http_requires_explicit_allowlist() -> None:
    with httpx.Client() as http:
        with pytest.raises(ValueError, match="HTTPS"):
            HttpKmsSecretBackend(
                http,
                "http://kms-adapter:8000",
                "kms-service-token",
            )
        with pytest.raises(ValueError, match="HTTPS"):
            HttpRiskAuthorizer(
                http,
                "http://risk:8000",
                "risk-service-token",
            )
        with pytest.raises(ValueError, match="HTTPS"):
            HttpKmsSecretBackend(
                http,
                "http://untrusted.example.com",
                "kms-service-token",
                allow_insecure_internal_http=True,
            )

        HttpKmsSecretBackend(
            http,
            "http://kms-adapter:8000",
            "kms-service-token",
            allow_insecure_internal_http=True,
        )
        HttpRiskAuthorizer(
            http,
            "http://risk:8000",
            "risk-service-token",
            allow_insecure_internal_http=True,
        )


def test_secret_backend_contract_rejects_cross_tenant_access() -> None:
    backend = InMemoryEncryptedSecretBackend()
    secret_ref = backend.put("tenant-a", {"api_key": "secret"})

    with pytest.raises(KeyError):
        backend.get("tenant-b", secret_ref)
    with pytest.raises(KeyError):
        backend.delete("tenant-b", secret_ref)

    assert backend.get("tenant-a", secret_ref) == {"api_key": "secret"}


def test_kms_client_sends_bearer_token_and_tenant_on_every_operation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/secrets":
            return httpx.Response(
                201,
                json={"secret_ref": "volc-kms://tenant-a/secret-a"},
            )
        if request.url.path == "/v1/secrets/resolve":
            return httpx.Response(200, json={"value": {"api_key": "secret"}})
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        backend = HttpKmsSecretBackend(
            http,
            "https://kms.internal",
            "kms-service-token",
        )
        secret_ref = backend.put("tenant-a", {"api_key": "secret"})
        assert backend.get("tenant-a", secret_ref) == {"api_key": "secret"}
        backend.delete("tenant-a", secret_ref)

    assert [request.url.path for request in requests] == [
        "/v1/secrets",
        "/v1/secrets/resolve",
        "/v1/secrets/delete",
    ]
    for request in requests:
        assert request.headers["Authorization"] == "Bearer kms-service-token"
        assert json.loads(request.content)["tenant_id"] == "tenant-a"


def test_risk_client_sends_service_and_single_use_approval_tokens() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"approved": len(requests) == 1})

    order = {
        "account_scope": "spot",
        "symbol": "BTCUSDT",
        "side": "buy",
        "order_type": "limit",
        "quantity": "0.01",
        "limit_price": "50000",
        "reduce_only": False,
        "source": "manual",
    }
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        authorizer = HttpRiskAuthorizer(
            http,
            "https://risk.internal",
            "risk-service-token",
        )
        first = authorizer.authorize(
            tenant_id="tenant-a",
            account_id="account-a",
            order=order,
            approval_token="single-use-approval",
        )
        replay = authorizer.authorize(
            tenant_id="tenant-a",
            account_id="account-a",
            order=order,
            approval_token="single-use-approval",
        )

    assert first is True
    assert replay is False
    assert len(requests) == 2
    for request in requests:
        assert request.headers["X-Service-Token"] == "risk-service-token"
        assert request.headers["X-Risk-Approval"] == "single-use-approval"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"approved": False}),
    ],
)
def test_risk_client_fails_closed(response: httpx.Response) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as http:
        authorizer = HttpRiskAuthorizer(
            http,
            "https://risk.internal",
            "risk-service-token",
        )

        approved = authorizer.authorize(
            tenant_id="tenant-a",
            account_id="account-a",
            order={},
            approval_token="approval-token",
        )

    assert approved is False


def test_risk_client_fails_closed_on_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("risk timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as http:
        authorizer = HttpRiskAuthorizer(
            http,
            "https://risk.internal",
            "risk-service-token",
        )

        approved = authorizer.authorize(
            tenant_id="tenant-a",
            account_id="account-a",
            order={},
            approval_token="approval-token",
        )

    assert approved is False
