import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime, UUID)):
        return str(value)
    raise TypeError(f"Unsupported value for request fingerprint: {type(value).__name__}")


def request_fingerprint(
    tenant_id: str,
    method: str,
    path: str,
    payload: Any,
) -> str:
    canonical_request = {
        "method": method.upper(),
        "path": path,
        "payload": payload,
        "tenant_id": tenant_id,
    }
    encoded = json.dumps(
        canonical_request,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
