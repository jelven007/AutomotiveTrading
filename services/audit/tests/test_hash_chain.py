from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from audit.consumer import AUDIT_TOPIC, AuditConsumer, AuditEvent
from audit.hash_chain import AuditLog, ImmutableAuditError
from audit.models import AuditRecord, Base
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


def event(event_id: str, tenant_id: str = "tenant-a") -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        actor_type="user",
        actor_id="user-1",
        action=f"strategy.updated.{event_id}",
        resource_type="strategy",
        resource_id="strategy-1",
        before_ref="s3://audit/before.json",
        after_ref="s3://audit/after.json",
        trace_id="trace-1",
        occurred_at=datetime(2026, 9, 18, 3, 0, tzinfo=UTC),
    )


def test_hash_chain_detects_tampering(session: Session) -> None:
    log = AuditLog(session)
    records = [log.append(event(f"event-{index}")) for index in range(1, 4)]
    assert log.verify_chain("tenant-a") is True

    session.execute(
        update(AuditRecord).where(AuditRecord.id == records[1].id).values(action="strategy.deleted")
    )
    session.commit()

    assert log.verify_chain("tenant-a") is False


def test_consumer_is_idempotent_by_event_id(session: Session) -> None:
    consumer = AuditConsumer(AuditLog(session))
    payload = event("event-1").to_payload()

    first = consumer.consume(AUDIT_TOPIC, payload)
    second = consumer.consume(AUDIT_TOPIC, payload)

    assert first.id == second.id
    assert session.scalar(select(func.count()).select_from(AuditRecord)) == 1


def test_query_is_always_scoped_to_tenant(session: Session) -> None:
    log = AuditLog(session)
    log.append(event("event-a", tenant_id="tenant-a"))
    log.append(event("event-b", tenant_id="tenant-b"))

    records = log.list_for_tenant("tenant-a")

    assert [record.event_id for record in records] == ["event-a"]


def test_records_reject_orm_updates_and_deletes(session: Session) -> None:
    record = AuditLog(session).append(event("event-1"))
    record.action = "strategy.deleted"

    with pytest.raises(ImmutableAuditError):
        session.commit()
    session.rollback()

    persisted = session.get(AuditRecord, record.id)
    assert persisted is not None
    session.delete(persisted)
    with pytest.raises(ImmutableAuditError):
        session.commit()
