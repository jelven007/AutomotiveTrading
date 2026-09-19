import hashlib
import json
from collections.abc import Iterator

import pytest
from kms_adapter.db import Base
from kms_adapter.models import ManagedSecret
from kms_adapter.provider import GeneratedDataKey
from kms_adapter.service import (
    EnvelopeSecretService,
    SecretIntegrityError,
    SecretNotFoundError,
    SecretPersistenceError,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class FakeKmsProvider:
    def __init__(self) -> None:
        self.generated_contexts: list[dict[str, str]] = []
        self.decrypted_contexts: list[dict[str, str]] = []
        self._keys: dict[bytes, tuple[bytes, dict[str, str]]] = {}

    def generate_data_key(
        self,
        key_id: str,
        encryption_context: dict[str, str],
    ) -> GeneratedDataKey:
        del key_id
        key = hashlib.sha256(f"key-{len(self._keys)}".encode()).digest()
        wrapped = hashlib.sha256(key + str(len(self._keys)).encode()).digest()
        context = dict(encryption_context)
        self.generated_contexts.append(context)
        self._keys[wrapped] = (key, context)
        return GeneratedDataKey(plaintext=key, ciphertext=wrapped)

    def decrypt_data_key(
        self,
        encrypted_data_key: bytes,
        encryption_context: dict[str, str],
    ) -> bytes:
        key, expected_context = self._keys[encrypted_data_key]
        context = dict(encryption_context)
        self.decrypted_contexts.append(context)
        if context != expected_context:
            raise ValueError("encryption context mismatch")
        return key


@pytest.fixture
def session() -> Iterator[Session]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def provider() -> FakeKmsProvider:
    return FakeKmsProvider()


@pytest.fixture
def service(session: Session, provider: FakeKmsProvider) -> EnvelopeSecretService:
    return EnvelopeSecretService(
        session,
        provider,
        key_id="volc-key-id",
        purpose="binance-credentials",
    )


def test_put_encrypts_secret_with_bound_context(
    session: Session,
    provider: FakeKmsProvider,
    service: EnvelopeSecretService,
) -> None:
    secret = {"api_key": "production-api-key", "private_key": "private-material"}

    secret_ref = service.put("tenant-a", secret)
    record = session.scalar(select(ManagedSecret))

    assert record is not None
    assert secret_ref == f"volc-kms://tenant-a/{record.id}"
    assert record.nonce is not None and len(record.nonce) == 12
    assert record.ciphertext is not None
    assert b"production-api-key" not in record.ciphertext
    assert b"private-material" not in record.ciphertext
    assert provider.generated_contexts == [
        {
            "purpose": "binance-credentials",
            "secret_id": record.id,
            "tenant_id": "tenant-a",
        }
    ]
    assert json.loads(record.encryption_context_json or "{}") == provider.generated_contexts[0]
    assert service.resolve("tenant-a", secret_ref) == secret
    assert provider.decrypted_contexts == provider.generated_contexts


def test_same_secret_uses_distinct_nonce_and_ciphertext(
    session: Session,
    service: EnvelopeSecretService,
) -> None:
    first_ref = service.put("tenant-a", {"api_key": "same-value"})
    second_ref = service.put("tenant-a", {"api_key": "same-value"})
    records = list(session.scalars(select(ManagedSecret).order_by(ManagedSecret.created_at)))

    assert first_ref != second_ref
    assert len(records) == 2
    assert records[0].nonce != records[1].nonce
    assert records[0].ciphertext != records[1].ciphertext


def test_cross_tenant_resolve_and_delete_are_rejected(
    service: EnvelopeSecretService,
) -> None:
    secret_ref = service.put("tenant-a", {"api_key": "secret"})

    with pytest.raises(SecretNotFoundError):
        service.resolve("tenant-b", secret_ref)
    with pytest.raises(SecretNotFoundError):
        service.delete("tenant-b", secret_ref)

    assert service.resolve("tenant-a", secret_ref) == {"api_key": "secret"}


@pytest.mark.parametrize("field", ["ciphertext", "encryption_context_json"])
def test_tampering_is_rejected(
    session: Session,
    service: EnvelopeSecretService,
    field: str,
) -> None:
    secret_ref = service.put("tenant-a", {"api_key": "secret"})
    record = session.scalar(select(ManagedSecret))
    assert record is not None
    if field == "ciphertext":
        assert record.ciphertext is not None
        record.ciphertext = record.ciphertext[:-1] + bytes([record.ciphertext[-1] ^ 1])
    else:
        record.encryption_context_json = json.dumps(
            {
                "purpose": "different-purpose",
                "secret_id": record.id,
                "tenant_id": record.tenant_id,
            }
        )
    session.commit()

    with pytest.raises(SecretIntegrityError):
        service.resolve("tenant-a", secret_ref)


def test_delete_removes_all_recovery_material(
    session: Session,
    service: EnvelopeSecretService,
) -> None:
    secret_ref = service.put("tenant-a", {"api_key": "secret"})

    service.delete("tenant-a", secret_ref)
    record = session.scalar(select(ManagedSecret))

    assert record is not None
    assert record.status == "deleted"
    assert record.deleted_at is not None
    assert record.key_id is None
    assert record.encrypted_data_key is None
    assert record.nonce is None
    assert record.ciphertext is None
    assert record.encryption_context_json is None
    assert record.purpose is None
    with pytest.raises(SecretNotFoundError):
        service.resolve("tenant-a", secret_ref)


def test_failed_commit_rolls_back_partial_record(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    service: EnvelopeSecretService,
) -> None:
    real_rollback = session.rollback
    rollback_called = False

    def tracked_rollback() -> None:
        nonlocal rollback_called
        rollback_called = True
        real_rollback()

    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError()))
    monkeypatch.setattr(session, "rollback", tracked_rollback)

    with pytest.raises(SecretPersistenceError):
        service.put("tenant-a", {"api_key": "secret"})

    assert rollback_called is True
    assert session.scalar(select(func.count()).select_from(ManagedSecret)) == 0
