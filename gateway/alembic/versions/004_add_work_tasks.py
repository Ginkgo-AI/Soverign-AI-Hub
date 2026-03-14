"""Add work_tasks table and work_mode fields to agent_executions.

Revision ID: 004_work_tasks
Revises: 003_skills
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_work_tasks"
down_revision = "003_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add work mode columns to agent_executions
    op.add_column("agent_executions", sa.Column("objective", sa.Text, nullable=True))
    op.add_column("agent_executions", sa.Column("work_mode", sa.Boolean, server_default="false"))

    op.create_table(
        "work_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_executions.id", ondelete="CASCADE"), index=True),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_tasks.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("depends_on", postgresql.JSON, server_default="[]"),
        sa.Column("task_order", sa.Integer, server_default="0"),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("work_tasks")
    op.drop_column("agent_executions", "work_mode")
    op.drop_column("agent_executions", "objective")
