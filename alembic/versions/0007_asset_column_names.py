"""rename asset foreign key columns

Revision ID: 0007_asset_column_names
Revises: 0006_asset_table_names
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_asset_column_names"
down_revision = "0006_asset_table_names"
branch_labels = None
depends_on = None


ASSET_LINK_TABLES = (
    "run_inputs",
    "run_outputs",
    "asset_versions",
    "job_version_io_mapping",
    "asset_facets",
)


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _constraints(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {item["name"] for item in inspector.get_unique_constraints(table_name)}


def _rename_constraint(table_name: str, old_name: str, new_name: str) -> None:
    constraints = _constraints(table_name)
    if old_name in constraints and new_name not in constraints:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )
        )


def _rename_column(table_name: str, old_name: str, new_name: str) -> None:
    columns = _columns(table_name)
    if old_name in columns and new_name not in columns:
        op.alter_column(table_name, old_name, new_column_name=new_name)


def upgrade() -> None:
    for table_name in ASSET_LINK_TABLES:
        _rename_column(table_name, "dataset_id", "asset_id")
    _rename_constraint(
        "job_version_io_mapping",
        "uq_job_version_dataset_iotype",
        "uq_job_version_asset_iotype",
    )


def downgrade() -> None:
    _rename_constraint(
        "job_version_io_mapping",
        "uq_job_version_asset_iotype",
        "uq_job_version_dataset_iotype",
    )
    for table_name in ASSET_LINK_TABLES:
        _rename_column(table_name, "asset_id", "dataset_id")
