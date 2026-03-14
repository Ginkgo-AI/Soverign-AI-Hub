"""Add skills table.

Revision ID: 003_skills
Revises: 002_memory_tables
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_skills"
down_revision = "002_memory_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("version", sa.String(50), server_default="1.0.0"),
        sa.Column("category", sa.String(100), nullable=False, index=True),
        sa.Column("catalog_summary", sa.String(500), server_default=""),
        sa.Column("icon", sa.String(50), server_default="sparkles"),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("tool_configuration", postgresql.JSON, server_default="[]"),
        sa.Column("example_prompts", postgresql.JSON, server_default="[]"),
        sa.Column("parameters", postgresql.JSON, server_default="{}"),
        sa.Column("source_type", sa.String(50), server_default="builtin"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("skills")
