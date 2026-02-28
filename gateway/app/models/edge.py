"""Database models for Edge Device management — Phase 8."""

import uuid

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EdgeDevice(UUIDMixin, TimestampMixin, Base):
    """Represents a registered edge agent that can sync with the hub."""

    __tablename__ = "edge_devices"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active, inactive, revoked
    last_seen: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_version: Mapped[str] = mapped_column(String(50), default="1")
    classification_level: Mapped[str] = mapped_column(
        String(50), default="UNCLASSIFIED"
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class EdgeSyncLog(Base):
    """Records each sync event between an edge device and the hub."""

    __tablename__ = "edge_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    sync_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # conversations, knowledge, config, models
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # push, pull
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="success"
    )  # success, error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
