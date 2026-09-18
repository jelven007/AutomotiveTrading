from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet


class SecretBackend(Protocol):
    def put(self, tenant_id: str, value: str) -> str: ...

    def get(self, secret_ref: str) -> str: ...

    def delete(self, secret_ref: str) -> None: ...


class LocalEncryptedSecretBackend:
    """Development-only encrypted backend implementing the production KMS contract."""

    def __init__(self, encryption_key: str) -> None:
        self._cipher = Fernet(encryption_key.encode())
        self._secrets: dict[str, bytes] = {}

    def put(self, tenant_id: str, value: str) -> str:
        secret_ref = f"local-kms://{tenant_id}/{uuid4()}"
        self._secrets[secret_ref] = self._cipher.encrypt(value.encode())
        return secret_ref

    def get(self, secret_ref: str) -> str:
        encrypted = self._secrets.get(secret_ref)
        if encrypted is None:
            raise KeyError("secret reference does not exist")
        return self._cipher.decrypt(encrypted).decode()

    def delete(self, secret_ref: str) -> None:
        self._secrets.pop(secret_ref, None)
