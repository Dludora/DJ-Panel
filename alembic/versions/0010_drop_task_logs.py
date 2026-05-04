"""drop task_logs in favor of log artifacts

Revision ID: 0010_drop_task_logs
Revises: 0009_command_submissions
Create Date: 2026-04-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_drop_task_logs"
down_revision = "0009_command_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("task_logs")


def downgrade() -> None:
    op.create_table(
        "task_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(length=36),
            sa.ForeignKey("task_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stream", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
