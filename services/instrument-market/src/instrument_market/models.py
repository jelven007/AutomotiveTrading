from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class ProviderCapability(Base):
    __tablename__ = "provider_capabilities"
    __table_args__ = (UniqueConstraint("provider", "market", "dataset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class CollectorJob(Base):
    __tablename__ = "collector_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    shard_id: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JobStatus.PENDING)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)


class CollectorCheckpoint(Base):
    __tablename__ = "collector_checkpoints"
    __table_args__ = (UniqueConstraint("dataset", "shard_id", "cursor_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    shard_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor_key: Mapped[str] = mapped_column(String(160), nullable=False)
    cursor_value: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exchange: Mapped[str | None] = mapped_column(String(16))
    symbol: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class RawObjectManifest(Base):
    __tablename__ = "raw_object_manifests"
    __table_args__ = (UniqueConstraint("bucket", "object_key", "content_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
