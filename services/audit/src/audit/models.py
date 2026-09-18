from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ImmutableAuditError(RuntimeError):
    pass


class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (
        UniqueConstraint("event_id"),
        UniqueConstraint("tenant_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    after_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)


def _reject_mutation(_: Mapper[AuditRecord], __: object, ___: AuditRecord) -> None:
    raise ImmutableAuditError("audit records are append-only")


event.listen(AuditRecord, "before_update", _reject_mutation)
event.listen(AuditRecord, "before_delete", _reject_mutation)
