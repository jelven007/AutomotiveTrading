import json
from typing import Any

from sqlalchemy.orm import Session

from trading.models import OutboxEvent

SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "secret",
        "private_key",
        "private_key_or_secret",
        "authorization",
    }
)


class SqlOutboxPublisher:
    def __init__(self, session: Session) -> None:
        self.session = session

    def publish(
        self,
        *,
        tenant_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
    ) -> None:
        self._reject_sensitive_payload(payload)
        self.session.add(
            OutboxEvent(
                tenant_id=tenant_id,
                topic="trading.events.v1",
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload_json=json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        )

    @classmethod
    def _reject_sensitive_payload(cls, payload: dict[str, Any]) -> None:
        for key, value in payload.items():
            normalized_key = key.lower()
            if normalized_key in SENSITIVE_KEYS or "password" in normalized_key:
                raise ValueError("sensitive values are forbidden in outbox payloads")
            if isinstance(value, dict):
                cls._reject_sensitive_payload(value)
