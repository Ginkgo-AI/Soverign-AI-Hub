"""Plugin tool model — dynamically loaded tools from the database."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PluginTool(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plugin_tools"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(50), default="0.1.0")
    category: Mapped[str] = mapped_column(String(100), default="plugin")
    parameters_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    handler_module: Mapped[str] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), default="upload")  # upload, builtin
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
