from collections.abc import Iterator

import pytest
from identity_tenant.auth import AuthService, AuthSettings
from identity_tenant.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def auth_service(session: Session) -> AuthService:
    settings = AuthSettings(
        issuer="https://identity.quant.test",
        audience="quant-api",
        jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
        totp_encryption_key="5J7v-vVVlNNJAapSF9Pn5FYe8sPKYB8A6t4s4R_7C2k=",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=3600,
    )
    return AuthService(session, settings)
