import base64
import hashlib
import hmac

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from trading.binance.signing import BinanceSigner
from trading.models import CredentialType

PAYLOAD = "symbol=BTCUSDT&side=BUY&timestamp=1668481559918"


def test_hmac_signature_uses_sha256_hex_digest() -> None:
    secret = "test-hmac-secret"

    signature = BinanceSigner.sign(CredentialType.HMAC, secret, PAYLOAD)

    expected = hmac.new(secret.encode(), PAYLOAD.encode(), hashlib.sha256).hexdigest()
    assert signature == expected


def test_ed25519_signature_can_be_verified() -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    signature = BinanceSigner.sign(CredentialType.ED25519, pem, PAYLOAD)

    private_key.public_key().verify(base64.b64decode(signature), PAYLOAD.encode())


def test_rsa_signature_uses_pkcs1v15_and_sha256() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    signature = BinanceSigner.sign(CredentialType.RSA, pem, PAYLOAD)

    private_key.public_key().verify(
        base64.b64decode(signature),
        PAYLOAD.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
