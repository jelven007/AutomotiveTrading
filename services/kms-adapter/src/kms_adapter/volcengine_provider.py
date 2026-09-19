import base64
import binascii
import importlib
from collections.abc import Callable
from typing import Any, Protocol, cast

from kms_adapter.provider import GeneratedDataKey, KmsProviderError


class _KmsApi(Protocol):
    def generate_data_key(self, request: object) -> object: ...

    def decrypt(self, request: object) -> object: ...


class _KmsModels(Protocol):
    GenerateDataKeyRequest: Callable[..., object]
    DecryptRequest: Callable[..., object]


SdkLoader = Callable[[], tuple[_KmsApi, _KmsModels]]


class VolcengineKmsProvider:
    def __init__(
        self,
        *,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        region: str = "cn-beijing",
        sdk_loader: SdkLoader | None = None,
    ) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._session_token = session_token
        self._region = region
        self._sdk_loader = sdk_loader or self._load_default_sdk
        self._sdk: tuple[_KmsApi, _KmsModels] | None = None

    def generate_data_key(
        self,
        key_id: str,
        encryption_context: dict[str, str],
    ) -> GeneratedDataKey:
        try:
            api, models = self._get_sdk()
            request = models.GenerateDataKeyRequest(
                key_id=key_id,
                number_of_bytes=32,
                encryption_context=dict(encryption_context),
            )
            response = api.generate_data_key(request)
        except Exception:
            raise KmsProviderError("Volcengine KMS request failed") from None

        plaintext = self._decode_plaintext(response)
        ciphertext_blob = getattr(response, "ciphertext_blob", None)
        if not isinstance(ciphertext_blob, str) or not ciphertext_blob:
            raise KmsProviderError("Volcengine KMS returned an invalid response")
        try:
            base64.b64decode(ciphertext_blob, validate=True)
            ciphertext = ciphertext_blob.encode("ascii")
        except (UnicodeEncodeError, ValueError, binascii.Error):
            raise KmsProviderError("Volcengine KMS returned an invalid response") from None
        return GeneratedDataKey(plaintext=plaintext, ciphertext=ciphertext)

    def decrypt_data_key(
        self,
        encrypted_data_key: bytes,
        encryption_context: dict[str, str],
    ) -> bytes:
        try:
            ciphertext_blob = encrypted_data_key.decode("ascii")
            api, models = self._get_sdk()
            request = models.DecryptRequest(
                ciphertext_blob=ciphertext_blob,
                encryption_context=dict(encryption_context),
            )
            response = api.decrypt(request)
        except Exception:
            raise KmsProviderError("Volcengine KMS request failed") from None
        return self._decode_plaintext(response)

    def _get_sdk(self) -> tuple[_KmsApi, _KmsModels]:
        if self._sdk is None:
            self._sdk = self._sdk_loader()
        return self._sdk

    def _load_default_sdk(self) -> tuple[_KmsApi, _KmsModels]:
        core = importlib.import_module("volcenginesdkcore")
        kms = importlib.import_module("volcenginesdkkms")
        configuration_factory = cast(Callable[[], Any], core.Configuration)
        api_client_factory = cast(Callable[[Any], Any], core.ApiClient)
        kms_api_factory = cast(Callable[[Any], Any], kms.KMSApi)

        configuration = configuration_factory()
        configuration.region = self._region
        if self._access_key is not None:
            configuration.ak = self._access_key
        if self._secret_key is not None:
            configuration.sk = self._secret_key
        if self._session_token is not None:
            configuration.session_token = self._session_token
        api = kms_api_factory(api_client_factory(configuration))
        return cast(_KmsApi, api), cast(_KmsModels, kms)

    @staticmethod
    def _decode_plaintext(response: object) -> bytes:
        plaintext = getattr(response, "plaintext", None)
        if not isinstance(plaintext, str):
            raise KmsProviderError("Volcengine KMS returned an invalid response")
        try:
            decoded = base64.b64decode(plaintext, validate=True)
        except (ValueError, binascii.Error):
            raise KmsProviderError("Volcengine KMS returned an invalid response") from None
        if len(decoded) != 32:
            raise KmsProviderError("Volcengine KMS returned an invalid response")
        return decoded
