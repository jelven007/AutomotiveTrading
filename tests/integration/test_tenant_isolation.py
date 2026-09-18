from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from identity_tenant.api.app import create_app
from identity_tenant.auth import AuthService, AuthSettings
from identity_tenant.db import get_session
from identity_tenant.models import Base, Role, TenantMember
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client_and_service() -> Iterator[tuple[TestClient, AuthService]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    settings = AuthSettings(
        issuer="https://identity.quant.test",
        audience="quant-api",
        jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
        totp_encryption_key="5J7v-vVVlNNJAapSF9Pn5FYe8sPKYB8A6t4s4R_7C2k=",
    )
    service = AuthService(session, settings)
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client, service
    session.close()


def test_tenant_from_token_cannot_access_another_tenant(
    client_and_service: tuple[TestClient, AuthService],
) -> None:
    client, service = client_and_service
    tenant_a = service.register(
        email="a@example.com",
        display_name="Tenant A Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Tenant A",
    )
    tenant_b = service.register(
        email="b@example.com",
        display_name="Tenant B Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Tenant B",
    )
    token_a = service.login(
        email="a@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=tenant_a.tenant_id,
    )

    response = client.get(
        f"/api/v1/tenants/{tenant_b.tenant_id}",
        headers={
            "Authorization": f"Bearer {token_a.access_token}",
            "X-Tenant-ID": tenant_b.tenant_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "resource.not_found"
    assert tenant_b.tenant_id not in response.text


def test_active_tenant_is_derived_from_token(
    client_and_service: tuple[TestClient, AuthService],
) -> None:
    client, service = client_and_service
    registration = service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    tokens = service.login(
        email="owner@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )

    response = client.get(
        f"/api/v1/tenants/{registration.tenant_id}",
        headers={
            "Authorization": f"Bearer {tokens.access_token}",
            "X-Tenant-ID": "forged-tenant-id",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == registration.tenant_id


def test_researcher_cannot_manage_tenant_members(
    client_and_service: tuple[TestClient, AuthService],
) -> None:
    client, service = client_and_service
    owner = service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    researcher = service.register(
        email="researcher@example.com",
        display_name="Researcher",
        password="Correct-Horse-Battery-99",
        tenant_name="Research Lab",
    )
    service.session.add(
        TenantMember(
            tenant_id=owner.tenant_id,
            user_id=researcher.user_id,
            role=Role.RESEARCHER,
        )
    )
    service.session.commit()
    tokens = service.login(
        email="researcher@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=owner.tenant_id,
    )

    response = client.post(
        f"/api/v1/tenants/{owner.tenant_id}/members",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
        json={"user_id": owner.user_id, "role": Role.AUDITOR.value},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization.denied"
