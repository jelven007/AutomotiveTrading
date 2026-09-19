import base64
import hashlib
import hmac

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from trading.binance.errors import BinanceConnectorError
from trading.models import CredentialType


class BinanceSigner:
    @staticmethod
    def sign(
        credential_type: CredentialType,
        private_key_or_secret: str,
        payload: str,
    ) -> str:
        if credential_type is CredentialType.HMAC:
            return hmac.new(
                private_key_or_secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()

        try:
            private_key = serialization.load_pem_private_key(
                private_key_or_secret.encode(),
                password=None,
            )
        except (TypeError, ValueError) as error:
            raise BinanceConnectorError(
                "binance.private_key_invalid",
                "Binance private key is invalid",
            ) from error

        if credential_type is CredentialType.ED25519:
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                raise BinanceConnectorError(
                    "binance.private_key_invalid",
                    "Expected an Ed25519 private key",
                )
            signature = private_key.sign(payload.encode())
        elif credential_type is CredentialType.RSA:
            if not isinstance(private_key, rsa.RSAPrivateKey):
                raise BinanceConnectorError(
                    "binance.private_key_invalid",
                    "Expected an RSA private key",
                )
            signature = private_key.sign(
                payload.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        else:
            raise BinanceConnectorError(
                "binance.credential_type_unsupported",
                "Binance credential type is unsupported",
            )
        return base64.b64encode(signature).decode()
