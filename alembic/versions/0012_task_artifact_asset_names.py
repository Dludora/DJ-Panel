"""rename task artifact dataset columns to asset columns

Revision ID: 0012_task_artifact_asset_names
Revises: 0011_asset_catalog_and_execution_links
Create Date: 2026-05-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_task_artifact_asset_names"
down_revision = "0011_asset_catalog_and_execution_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_artifacts") as batch_op:
        batch_op.alter_column(
            "dataset_id",
            new_column_name="asset_id",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "dataset_version_id",
            new_column_name="asset_version_id",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("task_artifacts") as batch_op:
        batch_op.alter_column(
            "asset_id",
            new_column_name="dataset_id",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "asset_version_id",
            new_column_name="dataset_version_id",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )
