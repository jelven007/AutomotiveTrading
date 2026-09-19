import json
from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from trading.models import LocalEncryptedSecret


class SecretBackend(Protocol):
    def put(self, tenant_id: str, value: dict[str, str]) -> str: ...

    def get(self, secret_ref: str) -> dict[str, str]: ...

    def delete(self, secret_ref: str) -> None: ...


class InMemoryEncryptedSecretBackend:
    """Encrypted in-memory backend for unit tests only."""

    def __init__(self) -> None:
        self._cipher = Fernet(Fernet.generate_key())
        self._secrets: dict[str, bytes] = {}

    @property
    def count(self) -> int:
        return len(self._secrets)

    def put(self, tenant_id: str, value: dict[str, str]) -> str:
        secret_ref = f"memory-kms://{tenant_id}/{uuid4()}"
        serialized = json.dumps(value, separators=(",", ":")).encode()
        self._secrets[secret_ref] = self._cipher.encrypt(serialized)
        return secret_ref

    def get(self, secret_ref: str) -> dict[str, str]:
        encrypted = self._secrets.get(secret_ref)
        if encrypted is None:
            raise KeyError("secret reference does not exist")
        payload = json.loads(self._cipher.decrypt(encrypted))
        return {str(key): str(value) for key, value in payload.items()}

    def delete(self, secret_ref: str) -> None:
        self._secrets.pop(secret_ref, None)


class LocalEncryptedSecretBackend:
    """Encrypted local backend that must not be used in production."""

    SCHEME = "local-kms://"

    def __init__(self, session: Session, encryption_key: str) -> None:
        self._session = session
        self._cipher = Fernet(encryption_key.encode())

    def put(self, tenant_id: str, value: dict[str, str]) -> str:
        serialized = json.dumps(value, separators=(",", ":")).encode()
        record = LocalEncryptedSecret(
            tenant_id=tenant_id,
            ciphertext=self._cipher.encrypt(serialized).decode(),
        )
        self._session.add(record)
        self._session.flush()
        return f"{self.SCHEME}{record.id}"

    def get(self, secret_ref: str) -> dict[str, str]:
        record = self._session.get(LocalEncryptedSecret, self._id(secret_ref))
        if record is None:
            raise KeyError("secret reference does not exist")
        payload = json.loads(self._cipher.decrypt(record.ciphertext.encode()))
        return {str(key): str(value) for key, value in payload.items()}

    def delete(self, secret_ref: str) -> None:
        record = self._session.get(LocalEncryptedSecret, self._id(secret_ref))
        if record is not None:
            self._session.delete(record)

    @classmethod
    def _id(cls, secret_ref: str) -> str:
        if not secret_ref.startswith(cls.SCHEME):
            raise ValueError("unsupported secret reference")
        return secret_ref.removeprefix(cls.SCHEME)
