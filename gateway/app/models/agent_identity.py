"""Agent identity model — cryptographic action signing and verification."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AgentAction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_actions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id"), index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_executions.id"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(50))  # tool_call, response
    action_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    signature: Mapped[str] = mapped_column(Text)  # ed25519 base64
    payload_summary: Mapped[str] = mapped_column(Text, default="")
