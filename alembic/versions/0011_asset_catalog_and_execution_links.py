"""add asset catalog source and explicit execution links

Revision ID: 0011_asset_catalog_and_execution_links
Revises: 0010_drop_task_logs
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_asset_catalog_and_execution_links"
down_revision = "0010_drop_task_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "catalog_source",
                sa.String(length=32),
                nullable=False,
                server_default="LINEAGE_DISCOVERED",
            )
        )

    op.create_table(
        "execution_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_submission_id",
            sa.String(length=36),
            sa.ForeignKey("run_submissions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "task_attempt_id",
            sa.String(length=36),
            sa.ForeignKey("task_attempts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("openlineage_run_id", sa.String(length=255), nullable=False),
        sa.Column(
            "lineage_run_id",
            sa.String(length=36),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lineage_job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("task_attempt_id", name="uq_execution_links_attempt"),
        sa.UniqueConstraint(
            "openlineage_run_id", name="uq_execution_links_openlineage_run"
        ),
    )
    op.create_index(
        "ix_execution_links_run_submission",
        "execution_links",
        ["run_submission_id"],
    )
    op.create_index("ix_execution_links_task", "execution_links", ["task_id"])
    op.create_index(
        "ix_execution_links_openlineage_run",
        "execution_links",
        ["openlineage_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_links_openlineage_run", table_name="execution_links")
    op.drop_index("ix_execution_links_task", table_name="execution_links")
    op.drop_index("ix_execution_links_run_submission", table_name="execution_links")
    op.drop_table("execution_links")

    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("catalog_source")
