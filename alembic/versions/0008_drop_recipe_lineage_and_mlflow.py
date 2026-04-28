"""drop recipe lineage columns and task attempt mlflow id

Revision ID: 0008_drop_recipe_lineage_and_mlflow
Revises: 0007_asset_column_names
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_drop_recipe_lineage_and_mlflow"
down_revision = "0007_asset_column_names"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    recipe_version_columns = _columns("recipe_versions")
    if "lineage_namespace" in recipe_version_columns:
        op.drop_column("recipe_versions", "lineage_namespace")
    if "lineage_job_name" in recipe_version_columns:
        op.drop_column("recipe_versions", "lineage_job_name")

    task_attempt_columns = _columns("task_attempts")
    if "mlflow_run_id" in task_attempt_columns:
        op.drop_column("task_attempts", "mlflow_run_id")


def downgrade() -> None:
    recipe_version_columns = _columns("recipe_versions")
    if "lineage_namespace" not in recipe_version_columns:
        op.add_column("recipe_versions", sa.Column("lineage_namespace", sa.Text(), nullable=True))
    if "lineage_job_name" not in recipe_version_columns:
        op.add_column("recipe_versions", sa.Column("lineage_job_name", sa.Text(), nullable=True))

    task_attempt_columns = _columns("task_attempts")
    if "mlflow_run_id" not in task_attempt_columns:
        op.add_column("task_attempts", sa.Column("mlflow_run_id", sa.String(length=255), nullable=True))
