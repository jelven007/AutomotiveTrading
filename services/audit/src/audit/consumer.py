from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from audit.hash_chain import AuditLog
from audit.models import AuditRecord

AUDIT_TOPIC = "audit.recorded.v1"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    tenant_id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    before_ref: str | None = None
    after_ref: str | None = None
    trace_id: str
    occurred_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AuditConsumer:
    def __init__(self, audit_log: AuditLog) -> None:
        self.audit_log = audit_log

    def consume(self, topic: str, payload: dict[str, Any]) -> AuditRecord:
        if topic != AUDIT_TOPIC:
            raise ValueError(f"unsupported audit topic: {topic}")
        return self.audit_log.append(AuditEvent.model_validate(payload))
