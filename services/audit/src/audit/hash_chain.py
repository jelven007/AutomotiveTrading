import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit.models import AuditRecord, ImmutableAuditError

if TYPE_CHECKING:
    from audit.consumer import AuditEvent

GENESIS_HASH = "0" * 64


class AuditEventConflictError(RuntimeError):
    pass


class AuditLog:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, audit_event: "AuditEvent") -> AuditRecord:
        existing = self.session.scalar(
            select(AuditRecord).where(AuditRecord.event_id == audit_event.event_id)
        )
        if existing is not None:
            expected_hash = self._calculate_hash(
                self._event_payload(audit_event),
                existing.sequence,
                existing.previous_hash,
            )
            if not hmac.compare_digest(existing.record_hash, expected_hash):
                raise AuditEventConflictError("event_id already exists with different content")
            return existing

        previous = self.session.scalar(
            select(AuditRecord)
            .where(AuditRecord.tenant_id == audit_event.tenant_id)
            .order_by(AuditRecord.sequence.desc())
            .limit(1)
            .with_for_update()
        )
        sequence = 1 if previous is None else previous.sequence + 1
        previous_hash = GENESIS_HASH if previous is None else previous.record_hash
        fields = self._event_payload(audit_event)
        record = AuditRecord(
            **fields,
            sequence=sequence,
            previous_hash=previous_hash,
            record_hash=self._calculate_hash(fields, sequence, previous_hash),
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            concurrent = self.session.scalar(
                select(AuditRecord).where(AuditRecord.event_id == audit_event.event_id)
            )
            if concurrent is not None:
                expected_hash = self._calculate_hash(
                    fields,
                    concurrent.sequence,
                    concurrent.previous_hash,
                )
                if hmac.compare_digest(concurrent.record_hash, expected_hash):
                    return concurrent
            raise
        return record

    def list_for_tenant(self, tenant_id: str, limit: int = 100) -> list[AuditRecord]:
        return list(
            self.session.scalars(
                select(AuditRecord)
                .where(AuditRecord.tenant_id == tenant_id)
                .order_by(AuditRecord.sequence.desc())
                .limit(limit)
            )
        )

    def verify_chain(self, tenant_id: str) -> bool:
        records = self.session.scalars(
            select(AuditRecord)
            .where(AuditRecord.tenant_id == tenant_id)
            .order_by(AuditRecord.sequence)
        )
        previous_hash = GENESIS_HASH
        expected_sequence = 1
        for record in records:
            if record.sequence != expected_sequence or record.previous_hash != previous_hash:
                return False
            expected_hash = self._calculate_hash(
                self._event_fields(record),
                record.sequence,
                record.previous_hash,
            )
            if not hmac.compare_digest(record.record_hash, expected_hash):
                return False
            previous_hash = record.record_hash
            expected_sequence += 1
        return True

    @staticmethod
    def _event_payload(event: "AuditEvent") -> dict[str, Any]:
        return event.model_dump()

    @staticmethod
    def _event_fields(record: AuditRecord) -> dict[str, Any]:
        return {
            "event_id": record.event_id,
            "tenant_id": record.tenant_id,
            "actor_type": record.actor_type,
            "actor_id": record.actor_id,
            "action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "before_ref": record.before_ref,
            "after_ref": record.after_ref,
            "trace_id": record.trace_id,
            "occurred_at": record.occurred_at,
        }

    @staticmethod
    def _calculate_hash(fields: dict[str, Any], sequence: int, previous_hash: str) -> str:
        normalized_fields = dict(fields)
        occurred_at = normalized_fields["occurred_at"]
        if isinstance(occurred_at, datetime):
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            normalized_fields["occurred_at"] = occurred_at.astimezone(UTC).isoformat()
        canonical = json.dumps(
            {
                "sequence": sequence,
                "previous_hash": previous_hash,
                **normalized_fields,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = [
    "AuditEventConflictError",
    "AuditLog",
    "ImmutableAuditError",
]
