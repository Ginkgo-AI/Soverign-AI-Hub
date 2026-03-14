"""Add plugin_tools table.

Revision ID: 001_plugin_tools
Revises:
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_plugin_tools"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("version", sa.String(50), server_default="0.1.0"),
        sa.Column("category", sa.String(100), server_default="plugin"),
        sa.Column("parameters_schema", postgresql.JSON, server_default="{}"),
        sa.Column("handler_module", sa.Text, nullable=False),
        sa.Column("requires_approval", sa.Boolean, server_default="true"),
        sa.Column("enabled", sa.Boolean, server_default="false"),
        sa.Column("source", sa.String(50), server_default="upload"),
        sa.Column("manifest", postgresql.JSON, nullable=True),
        sa.Column("installed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("plugin_tools")
