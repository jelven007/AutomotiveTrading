import base64
from types import SimpleNamespace
from typing import Any

import pytest
from kms_adapter.provider import KmsProviderError
from kms_adapter.volcengine_provider import VolcengineKmsProvider


class RequestModel:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)


class FakeModels:
    GenerateDataKeyRequest = RequestModel
    DecryptRequest = RequestModel


class FakeKmsApi:
    def __init__(self) -> None:
        self.generated_requests: list[RequestModel] = []
        self.decrypted_requests: list[RequestModel] = []

    def generate_data_key(self, request: RequestModel) -> SimpleNamespace:
        self.generated_requests.append(request)
        return SimpleNamespace(
            plaintext=base64.b64encode(b"k" * 32).decode(),
            ciphertext_blob=base64.b64encode(b"wrapped-data-key").decode(),
        )

    def decrypt(self, request: RequestModel) -> SimpleNamespace:
        self.decrypted_requests.append(request)
        return SimpleNamespace(plaintext=base64.b64encode(b"k" * 32).decode())


def test_generate_and_decrypt_use_exact_context_and_32_byte_key() -> None:
    api = FakeKmsApi()
    provider = VolcengineKmsProvider(sdk_loader=lambda: (api, FakeModels()))
    context = {
        "tenant_id": "tenant-a",
        "secret_id": "secret-a",
        "purpose": "binance-credentials",
    }

    generated = provider.generate_data_key("volc-key-id", context)
    decrypted = provider.decrypt_data_key(generated.ciphertext, context)

    generate_request = api.generated_requests[0]
    decrypt_request = api.decrypted_requests[0]
    assert generate_request.key_id == "volc-key-id"
    assert generate_request.number_of_bytes == 32
    assert generate_request.encryption_context == context
    assert generated.plaintext == b"k" * 32
    assert generated.ciphertext == base64.b64encode(b"wrapped-data-key")
    assert decrypt_request.ciphertext_blob == generated.ciphertext.decode()
    assert decrypt_request.encryption_context == context
    assert decrypted == b"k" * 32


def test_sdk_is_loaded_lazily_and_only_once() -> None:
    api = FakeKmsApi()
    calls = 0

    def load_sdk() -> tuple[FakeKmsApi, FakeModels]:
        nonlocal calls
        calls += 1
        return api, FakeModels()

    provider = VolcengineKmsProvider(sdk_loader=load_sdk)

    assert calls == 0
    provider.generate_data_key("volc-key-id", {"tenant_id": "tenant-a"})
    provider.generate_data_key("volc-key-id", {"tenant_id": "tenant-a"})
    assert calls == 1


def test_cloud_errors_are_sanitized() -> None:
    access_key = "AKLT-do-not-leak"
    secret_key = "secret-key-do-not-leak"

    class FailingApi(FakeKmsApi):
        def generate_data_key(self, request: RequestModel) -> SimpleNamespace:
            del request
            raise RuntimeError(f"cloud rejected {access_key}:{secret_key}")

    provider = VolcengineKmsProvider(
        sdk_loader=lambda: (FailingApi(), FakeModels()),
    )

    with pytest.raises(KmsProviderError) as captured:
        provider.generate_data_key("volc-key-id", {"tenant_id": "tenant-a"})

    assert access_key not in str(captured.value)
    assert secret_key not in str(captured.value)
    assert str(captured.value) == "Volcengine KMS request failed"


def test_invalid_base64_response_is_rejected() -> None:
    class InvalidResponseApi(FakeKmsApi):
        def generate_data_key(self, request: RequestModel) -> SimpleNamespace:
            del request
            return SimpleNamespace(plaintext="not-valid-base64!", ciphertext_blob="wrapped")

    provider = VolcengineKmsProvider(
        sdk_loader=lambda: (InvalidResponseApi(), FakeModels()),
    )

    with pytest.raises(KmsProviderError, match="invalid response"):
        provider.generate_data_key("volc-key-id", {"tenant_id": "tenant-a"})
