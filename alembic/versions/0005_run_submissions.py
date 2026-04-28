"""rename recipe runs to run submissions

Revision ID: 0005_run_submissions
Revises: 0004_v1_asset_submission_fields
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "0005_run_submissions"
down_revision = "0004_v1_asset_submission_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "recipe_runs" in tables and "run_submissions" not in tables:
        op.rename_table("recipe_runs", "run_submissions")

    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "recipe_run_id" in task_columns and "run_submission_id" not in task_columns:
        op.alter_column("tasks", "recipe_run_id", new_column_name="run_submission_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "run_submission_id" in task_columns and "recipe_run_id" not in task_columns:
        op.alter_column("tasks", "run_submission_id", new_column_name="recipe_run_id")

    if "run_submissions" in tables and "recipe_runs" not in tables:
        op.rename_table("run_submissions", "recipe_runs")
