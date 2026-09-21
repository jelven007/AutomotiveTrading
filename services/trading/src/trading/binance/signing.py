import hashlib
import hmac


class BinanceSigner:
    @staticmethod
    def sign(secret: str, payload: str) -> str:
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
