"""drop internal run/job ids from execution links

Revision ID: 0017_execution_links_public_run_only
Revises: 0016_processing_submission_kind
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_execution_links_public_run_only"
down_revision = "0016_processing_submission_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("execution_links") as batch_op:
        batch_op.drop_column("lineage_job_id")
        batch_op.drop_column("lineage_run_id")


def downgrade() -> None:
    with op.batch_alter_table("execution_links") as batch_op:
        batch_op.add_column(
            sa.Column("lineage_run_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("lineage_job_id", sa.String(length=36), nullable=True)
        )
