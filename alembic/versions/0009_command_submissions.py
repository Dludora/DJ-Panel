"""add command submission support for training and evaluation

Revision ID: 0009_command_submissions
Revises: 0008_drop_recipe_lineage_and_mlflow
Create Date: 2026-04-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_command_submissions"
down_revision = "0008_drop_recipe_lineage_and_mlflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("run_submissions") as batch_op:
        batch_op.alter_column("recipe_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column(
            "recipe_version_id", existing_type=sa.String(length=36), nullable=True
        )
        batch_op.add_column(sa.Column("name", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "submission_kind",
                sa.String(length=64),
                nullable=False,
                server_default="processing_pipeline",
            )
        )
        batch_op.add_column(
            sa.Column("spec", sa.JSON(), nullable=False, server_default="{}")
        )

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "recipe_version_id", existing_type=sa.String(length=36), nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "recipe_version_id", existing_type=sa.String(length=36), nullable=False
        )

    with op.batch_alter_table("run_submissions") as batch_op:
        batch_op.drop_column("spec")
        batch_op.drop_column("submission_kind")
        batch_op.drop_column("name")
        batch_op.alter_column(
            "recipe_version_id", existing_type=sa.String(length=36), nullable=False
        )
        batch_op.alter_column("recipe_id", existing_type=sa.String(length=36), nullable=False)
