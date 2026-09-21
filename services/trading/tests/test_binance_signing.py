import hashlib
import hmac

from trading.binance.signing import BinanceSigner

PAYLOAD = "symbol=BTCUSDT&side=BUY&timestamp=1668481559918"


def test_hmac_signature_uses_sha256_hex_digest() -> None:
    secret = "test-hmac-secret"

    signature = BinanceSigner.sign(secret, PAYLOAD)

    expected = hmac.new(secret.encode(), PAYLOAD.encode(), hashlib.sha256).hexdigest()
    assert signature == expected
