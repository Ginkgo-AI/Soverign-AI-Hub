"""Skill model — packaged capabilities with system prompts and tool configs."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Skill(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    category: Mapped[str] = mapped_column(String(100), index=True)  # research, analysis, writing, coding
    catalog_summary: Mapped[str] = mapped_column(String(500), default="")
    icon: Mapped[str] = mapped_column(String(50), default="sparkles")
    system_prompt: Mapped[str] = mapped_column(Text)
    tool_configuration: Mapped[list] = mapped_column(JSON, default=list)  # list of tool names
    example_prompts: Mapped[list] = mapped_column(JSON, default=list)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(50), default="builtin")  # builtin, custom
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
