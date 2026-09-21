import base64
import hmac
import json
import os
import stat
from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import Session

from trading.models import LocalEncryptedSecret


class SecretBackend(Protocol):
    def put(self, tenant_id: str, value: dict[str, str]) -> str: ...

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]: ...

    def delete(self, tenant_id: str, secret_ref: str) -> None: ...


class LocalCredentialVault:
    """使用本地主密钥和 AES-GCM 保护币安凭据。"""

    VERSION = 1

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise ValueError("credential master key must be exactly 32 bytes")
        self._key = master_key

    @classmethod
    def from_file(cls, path: str) -> "LocalCredentialVault":
        file_stat = os.stat(path)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("credential master key must be a regular file")
        if file_stat.st_mode & 0o077:
            raise PermissionError("credential master key file must be readable only by owner")
        with open(path, "rb") as key_file:
            return cls(key_file.read())

    def encrypt(self, account_id: str, value: dict[str, str]) -> tuple[str, str, int]:
        nonce = os.urandom(12)
        aad = self._aad(account_id)
        ciphertext = AESGCM(self._key).encrypt(
            nonce, json.dumps(value, separators=(",", ":")).encode(), aad
        )
        return (
            base64.urlsafe_b64encode(ciphertext).decode(),
            base64.urlsafe_b64encode(nonce).decode(),
            self.VERSION,
        )

    def decrypt(
        self,
        account_id: str,
        ciphertext: str,
        nonce: str,
        version: int,
    ) -> dict[str, str]:
        if version != self.VERSION:
            raise ValueError("unsupported credential version")
        plaintext = AESGCM(self._key).decrypt(
            base64.urlsafe_b64decode(nonce),
            base64.urlsafe_b64decode(ciphertext),
            self._aad(account_id),
        )
        payload = json.loads(plaintext)
        return {str(key): str(item) for key, item in payload.items()}

    @staticmethod
    def _aad(account_id: str) -> bytes:
        return f"quant-trading:binance:{account_id}:v1".encode()


class LocalAesGcmSecretBackend:
    """Persist AES-GCM ciphertext locally; plaintext never reaches the database."""

    SCHEME = "local-aes-gcm://"

    def __init__(self, session: Session, vault: LocalCredentialVault) -> None:
        self._session = session
        self._vault = vault

    def put(self, tenant_id: str, value: dict[str, str]) -> str:
        record = LocalEncryptedSecret(tenant_id=tenant_id, ciphertext="")
        self._session.add(record)
        self._session.flush()
        ciphertext, nonce, version = self._vault.encrypt(record.id, value)
        record.ciphertext = ciphertext
        record.nonce = nonce
        record.version = version
        return f"{self.SCHEME}{record.id}"

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]:
        record = self._get_record(tenant_id, secret_ref)
        return self._vault.decrypt(record.id, record.ciphertext, record.nonce, record.version)

    def delete(self, tenant_id: str, secret_ref: str) -> None:
        record = self._get_record(tenant_id, secret_ref, missing_ok=True)
        if record is not None:
            self._session.delete(record)

    def _get_record(
        self, tenant_id: str, secret_ref: str, *, missing_ok: bool = False
    ) -> LocalEncryptedSecret:
        if not secret_ref.startswith(self.SCHEME):
            raise KeyError("secret reference does not exist")
        record = self._session.get(LocalEncryptedSecret, secret_ref.removeprefix(self.SCHEME))
        if record is None or not hmac.compare_digest(record.tenant_id, tenant_id):
            if missing_ok:
                return None  # type: ignore[return-value]
            raise KeyError("secret reference does not exist")
        return record


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

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]:
        self._require_tenant(tenant_id, secret_ref)
        encrypted = self._secrets.get(secret_ref)
        if encrypted is None:
            raise KeyError("secret reference does not exist")
        payload = json.loads(self._cipher.decrypt(encrypted))
        return {str(key): str(value) for key, value in payload.items()}

    def delete(self, tenant_id: str, secret_ref: str) -> None:
        self._require_tenant(tenant_id, secret_ref)
        self._secrets.pop(secret_ref, None)

    @staticmethod
    def _require_tenant(tenant_id: str, secret_ref: str) -> None:
        expected_prefix = f"memory-kms://{tenant_id}/"
        if not hmac.compare_digest(
            secret_ref[: len(expected_prefix)],
            expected_prefix,
        ):
            raise KeyError("secret reference does not exist")
