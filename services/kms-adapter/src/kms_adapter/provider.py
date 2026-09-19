from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedDataKey:
    plaintext: bytes
    ciphertext: bytes


class KmsProvider(Protocol):
    def generate_data_key(
        self,
        key_id: str,
        encryption_context: dict[str, str],
    ) -> GeneratedDataKey: ...

    def decrypt_data_key(
        self,
        encrypted_data_key: bytes,
        encryption_context: dict[str, str],
    ) -> bytes: ...


class KmsProviderError(RuntimeError):
    """Sanitized provider failure safe to expose to internal callers."""
