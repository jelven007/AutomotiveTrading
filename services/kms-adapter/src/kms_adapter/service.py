import hmac
import json
import secrets
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from kms_adapter.models import ManagedSecret, new_id, utc_now
from kms_adapter.provider import KmsProvider


class SecretNotFoundError(LookupError):
    pass


class SecretIntegrityError(RuntimeError):
    pass


class SecretUnavailableError(RuntimeError):
    pass


class SecretPersistenceError(RuntimeError):
    pass


class EnvelopeSecretService:
    SCHEME = "volc-kms://"

    def __init__(
        self,
        session: Session,
        provider: KmsProvider,
        *,
        key_id: str,
        purpose: str,
    ) -> None:
        if not key_id or not purpose:
            raise ValueError("key_id and purpose are required")
        self.session = session
        self.provider = provider
        self.key_id = key_id
        self.purpose = purpose

    def put(self, tenant_id: str, value: dict[str, str]) -> str:
        self._validate_value(value)
        record = ManagedSecret(
            id=new_id(),
            tenant_id=tenant_id,
            key_id=self.key_id,
            purpose=self.purpose,
        )
        context = self._context(record)
        context_bytes = self._canonical_json(context)
        try:
            data_key = self.provider.generate_data_key(self.key_id, context)
        except Exception as error:
            raise SecretUnavailableError("KMS data key generation failed") from error
        if len(data_key.plaintext) != 32 or not data_key.ciphertext:
            raise SecretUnavailableError("KMS returned invalid data key material")

        nonce = secrets.token_bytes(12)
        plaintext = self._canonical_json(value)
        ciphertext = AESGCM(data_key.plaintext).encrypt(nonce, plaintext, context_bytes)
        record.encrypted_data_key = data_key.ciphertext
        record.nonce = nonce
        record.ciphertext = ciphertext
        record.encryption_context_json = context_bytes.decode()
        self.session.add(record)
        try:
            self.session.commit()
        except SQLAlchemyError as error:
            self.session.rollback()
            raise SecretPersistenceError("secret persistence failed") from error
        return f"{self.SCHEME}{tenant_id}/{record.id}"

    def resolve(self, tenant_id: str, secret_ref: str) -> dict[str, str]:
        record = self._get_active_record(tenant_id, secret_ref)
        context = self._context(record)
        context_bytes = self._canonical_json(context)
        if (
            record.encryption_context_json is None
            or not hmac.compare_digest(record.encryption_context_json.encode(), context_bytes)
            or record.encrypted_data_key is None
            or record.nonce is None
            or record.ciphertext is None
        ):
            raise SecretIntegrityError("secret recovery material is invalid")

        try:
            data_key = self.provider.decrypt_data_key(record.encrypted_data_key, context)
        except Exception as error:
            raise SecretUnavailableError("KMS data key decryption failed") from error
        if len(data_key) != 32:
            raise SecretUnavailableError("KMS returned invalid data key material")

        try:
            plaintext = AESGCM(data_key).decrypt(
                record.nonce,
                record.ciphertext,
                context_bytes,
            )
            payload: Any = json.loads(plaintext)
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SecretIntegrityError("secret ciphertext integrity check failed") from error
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in payload.items()
        ):
            raise SecretIntegrityError("secret payload is invalid")
        return payload

    def delete(self, tenant_id: str, secret_ref: str) -> None:
        record = self._get_active_record(tenant_id, secret_ref)
        record.key_id = None
        record.encrypted_data_key = None
        record.nonce = None
        record.ciphertext = None
        record.encryption_context_json = None
        record.purpose = None
        record.status = "deleted"
        record.deleted_at = utc_now()
        try:
            self.session.commit()
        except SQLAlchemyError as error:
            self.session.rollback()
            raise SecretPersistenceError("secret deletion failed") from error

    def _get_active_record(self, tenant_id: str, secret_ref: str) -> ManagedSecret:
        ref_tenant, secret_id = self._parse_ref(secret_ref)
        if not hmac.compare_digest(ref_tenant, tenant_id):
            raise SecretNotFoundError("secret reference does not exist")
        record = self.session.scalar(
            select(ManagedSecret).where(
                ManagedSecret.id == secret_id,
                ManagedSecret.tenant_id == tenant_id,
                ManagedSecret.status == "active",
            )
        )
        if record is None:
            raise SecretNotFoundError("secret reference does not exist")
        return record

    def _context(self, record: ManagedSecret) -> dict[str, str]:
        if record.purpose is None:
            raise SecretIntegrityError("secret purpose is missing")
        return {
            "purpose": record.purpose,
            "secret_id": record.id,
            "tenant_id": record.tenant_id,
        }

    @classmethod
    def _parse_ref(cls, secret_ref: str) -> tuple[str, str]:
        if not secret_ref.startswith(cls.SCHEME):
            raise SecretNotFoundError("secret reference does not exist")
        tenant_id, separator, secret_id = secret_ref.removeprefix(cls.SCHEME).partition("/")
        if not separator or not tenant_id or not secret_id or "/" in secret_id:
            raise SecretNotFoundError("secret reference does not exist")
        return tenant_id, secret_id

    @staticmethod
    def _canonical_json(value: dict[str, str]) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()

    @staticmethod
    def _validate_value(value: dict[str, str]) -> None:
        if not value or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in value.items()
        ):
            raise ValueError("secret value must be a non-empty string mapping")
