import hmac
import json
from typing import Protocol
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from trading.internal_urls import validate_internal_service_url
from trading.models import LocalEncryptedSecret


class SecretBackend(Protocol):
    def put(self, tenant_id: str, value: dict[str, str]) -> str: ...

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]: ...

    def delete(self, tenant_id: str, secret_ref: str) -> None: ...


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

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]:
        record = self._session.get(LocalEncryptedSecret, self._id(secret_ref))
        if record is not None and not hmac.compare_digest(record.tenant_id, tenant_id):
            record = None
        if record is None:
            raise KeyError("secret reference does not exist")
        payload = json.loads(self._cipher.decrypt(record.ciphertext.encode()))
        return {str(key): str(value) for key, value in payload.items()}

    def delete(self, tenant_id: str, secret_ref: str) -> None:
        record = self._session.get(LocalEncryptedSecret, self._id(secret_ref))
        if record is None:
            return
        if not hmac.compare_digest(record.tenant_id, tenant_id):
            raise KeyError("secret reference does not exist")
        self._session.delete(record)

    @classmethod
    def _id(cls, secret_ref: str) -> str:
        if not secret_ref.startswith(cls.SCHEME):
            raise ValueError("unsupported secret reference")
        return secret_ref.removeprefix(cls.SCHEME)


class HttpKmsSecretBackend:
    """Adapter for the platform's internal KMS broker."""

    def __init__(
        self,
        http: httpx.Client,
        base_url: str,
        service_token: str,
        *,
        allow_insecure_internal_http: bool = False,
    ) -> None:
        validate_internal_service_url(
            base_url,
            service_host="kms-adapter",
            allow_insecure_internal_http=allow_insecure_internal_http,
        )
        if not service_token:
            raise ValueError("KMS service token is required")
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}

    def put(self, tenant_id: str, value: dict[str, str]) -> str:
        response = self._http.post(
            f"{self._base_url}/v1/secrets",
            headers=self._headers,
            json={"tenant_id": tenant_id, "value": value},
            timeout=5,
        )
        response.raise_for_status()
        secret_ref = response.json().get("secret_ref")
        if not isinstance(secret_ref, str) or not secret_ref:
            raise RuntimeError("KMS response is missing secret_ref")
        return secret_ref

    def get(self, tenant_id: str, secret_ref: str) -> dict[str, str]:
        response = self._http.post(
            f"{self._base_url}/v1/secrets/resolve",
            headers=self._headers,
            json={"tenant_id": tenant_id, "secret_ref": secret_ref},
            timeout=5,
        )
        response.raise_for_status()
        value = response.json().get("value")
        if not isinstance(value, dict):
            raise RuntimeError("KMS response is missing secret value")
        return {str(key): str(item) for key, item in value.items()}

    def delete(self, tenant_id: str, secret_ref: str) -> None:
        response = self._http.post(
            f"{self._base_url}/v1/secrets/delete",
            headers=self._headers,
            json={"tenant_id": tenant_id, "secret_ref": secret_ref},
            timeout=5,
        )
        response.raise_for_status()
