import hashlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from kms_adapter.api import get_envelope_service
from kms_adapter.config import get_settings
from kms_adapter.db import Base
from kms_adapter.main import create_app
from kms_adapter.provider import GeneratedDataKey
from kms_adapter.service import EnvelopeSecretService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class FakeKmsProvider:
    def __init__(self) -> None:
        self.keys: dict[bytes, bytes] = {}

    def generate_data_key(
        self,
        key_id: str,
        encryption_context: dict[str, str],
    ) -> GeneratedDataKey:
        material = f"{key_id}:{encryption_context['secret_id']}".encode()
        plaintext = hashlib.sha256(material).digest()
        encrypted = hashlib.sha256(plaintext).digest()
        self.keys[encrypted] = plaintext
        return GeneratedDataKey(plaintext=plaintext, ciphertext=encrypted)

    def decrypt_data_key(
        self,
        encrypted_data_key: bytes,
        encryption_context: dict[str, str],
    ) -> bytes:
        del encryption_context
        return self.keys[encrypted_data_key]


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(
        "SERVICE_TOKEN",
        "kms-service-token-that-is-at-least-32-bytes",
    )
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    service = EnvelopeSecretService(
        session,
        FakeKmsProvider(),
        key_id="volc-key-id",
        purpose="binance-credentials",
    )
    app = create_app()
    app.dependency_overrides[get_envelope_service] = lambda: service
    with TestClient(app) as client:
        yield client
    session.close()
    get_settings.cache_clear()


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer kms-service-token-that-is-at-least-32-bytes"}


def test_service_token_is_required(api_client: TestClient) -> None:
    missing = api_client.post(
        "/v1/secrets",
        json={"tenant_id": "tenant-a", "value": {"api_key": "secret"}},
    )
    invalid = api_client.post(
        "/v1/secrets",
        headers={"Authorization": "Bearer invalid-token"},
        json={"tenant_id": "tenant-a", "value": {"api_key": "secret"}},
    )

    assert missing.status_code == 401
    assert missing.json()["code"] == "auth.service_token_missing"
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "auth.service_token_invalid"


def test_create_resolve_and_irreversibly_delete_secret(api_client: TestClient) -> None:
    created = api_client.post(
        "/v1/secrets",
        headers=auth_headers(),
        json={
            "tenant_id": "tenant-a",
            "value": {"api_key": "production-key", "private_key": "private-material"},
        },
    )
    secret_ref = created.json()["secret_ref"]
    resolved = api_client.post(
        "/v1/secrets/resolve",
        headers=auth_headers(),
        json={"tenant_id": "tenant-a", "secret_ref": secret_ref},
    )
    deleted = api_client.post(
        "/v1/secrets/delete",
        headers=auth_headers(),
        json={"tenant_id": "tenant-a", "secret_ref": secret_ref},
    )
    after_delete = api_client.post(
        "/v1/secrets/resolve",
        headers=auth_headers(),
        json={"tenant_id": "tenant-a", "secret_ref": secret_ref},
    )

    assert created.status_code == 201
    assert secret_ref.startswith("volc-kms://tenant-a/")
    assert resolved.status_code == 200
    assert resolved.json() == {
        "value": {
            "api_key": "production-key",
            "private_key": "private-material",
        }
    }
    assert deleted.status_code == 204
    assert after_delete.status_code == 404
    assert after_delete.json()["code"] == "kms.secret_not_found"


def test_cross_tenant_access_returns_not_found(api_client: TestClient) -> None:
    created = api_client.post(
        "/v1/secrets",
        headers=auth_headers(),
        json={"tenant_id": "tenant-a", "value": {"api_key": "secret"}},
    )

    response = api_client.post(
        "/v1/secrets/resolve",
        headers=auth_headers(),
        json={
            "tenant_id": "tenant-b",
            "secret_ref": created.json()["secret_ref"],
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "kms.secret_not_found"
