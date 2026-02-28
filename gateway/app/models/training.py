"""Database models for fine-tuning, datasets, and A/B testing — Phase 7."""

import uuid

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class TrainingJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "training_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    base_model: Mapped[str] = mapped_column(String(255))
    dataset_path: Mapped[str] = mapped_column(String(1000))
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, failed, cancelled
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrainingDataset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "training_datasets"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(50))  # jsonl, csv, alpaca
    file_path: Mapped[str] = mapped_column(String(1000))
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    token_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ABTest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ab_tests"

    model_a: Mapped[str] = mapped_column(String(255))
    model_b: Mapped[str] = mapped_column(String(255))
    traffic_split: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active, paused, completed
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
