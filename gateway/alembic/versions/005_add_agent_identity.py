"""Add agent identity and actions table.

Revision ID: 005_agent_identity
Revises: 004_work_tasks
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_agent_identity"
down_revision = "004_work_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add identity columns to agent_definitions
    op.add_column("agent_definitions", sa.Column("public_key", sa.Text, nullable=True))
    op.add_column("agent_definitions", sa.Column("signing_key_hash", sa.String(128), nullable=True))

    # Add signature column to audit_log
    op.add_column("audit_log", sa.Column("signature", sa.Text, nullable=True))

    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_definitions.id"), index=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_executions.id"), index=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text, nullable=False),
        sa.Column("payload_summary", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("agent_actions")
    op.drop_column("audit_log", "signature")
    op.drop_column("agent_definitions", "signing_key_hash")
    op.drop_column("agent_definitions", "public_key")
