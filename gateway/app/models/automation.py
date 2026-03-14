"""Automation models — schedules, watchers, and automation logs."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Schedule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedules"

    name: Mapped[str] = mapped_column(String(255))
    cron_expression: Mapped[str] = mapped_column(String(100))
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id")
    )
    prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Watcher(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "watchers"

    name: Mapped[str] = mapped_column(String(255))
    watch_path: Mapped[str] = mapped_column(String(1024))
    file_pattern: Mapped[str] = mapped_column(String(255), default="*")
    action_type: Mapped[str] = mapped_column(String(20))  # ingest, agent
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id"), nullable=True
    )
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class AutomationLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "automation_logs"

    trigger_type: Mapped[str] = mapped_column(String(20))  # schedule, watcher
    trigger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(20))  # success, failed, skipped
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_executions.id"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
