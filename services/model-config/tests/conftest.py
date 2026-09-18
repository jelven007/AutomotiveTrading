from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from model_config.models import Base
from model_config.secrets import LocalEncryptedSecretBackend
from model_config.service import ModelConfigurationService
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
def secret_backend() -> LocalEncryptedSecretBackend:
    return LocalEncryptedSecretBackend(Fernet.generate_key().decode())


@pytest.fixture
def config_service(
    session: Session,
    secret_backend: LocalEncryptedSecretBackend,
) -> ModelConfigurationService:
    return ModelConfigurationService(session, secret_backend)
