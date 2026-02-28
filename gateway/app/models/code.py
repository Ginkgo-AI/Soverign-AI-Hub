"""Database models for Code Assistant -- Phase 5."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CodeWorkspace(UUIDMixin, TimestampMixin, Base):
    """A code workspace backed by a directory on disk."""

    __tablename__ = "code_workspaces"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    path: Mapped[str] = mapped_column(Text)  # absolute path on disk


class CodeSession(UUIDMixin, TimestampMixin, Base):
    """An interactive code execution session (like a Jupyter kernel)."""

    __tablename__ = "code_sessions"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    language: Mapped[str] = mapped_column(String(50), default="python")


class CodeExecution(UUIDMixin, TimestampMixin, Base):
    """A single code execution within a session."""

    __tablename__ = "code_executions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    code: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(50))
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    return_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    exit_code: Mapped[int] = mapped_column(Integer, default=0)
