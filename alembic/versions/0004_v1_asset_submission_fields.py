"""add v1 asset and task dispatch fields

Revision ID: 0004_v1_asset_submission_fields
Revises: 0003_merge_backend_heads
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_v1_asset_submission_fields"
down_revision = "0003_merge_backend_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("asset_kind", sa.String(length=64), nullable=False, server_default="DATASET"),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("storage_uri", sa.Text(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("task_kind", sa.String(length=64), nullable=False, server_default="generic_command"),
    )


def downgrade() -> None:
    op.drop_column("tasks", "task_kind")
    op.drop_column("dataset_versions", "storage_uri")
    op.drop_column("datasets", "asset_kind")
