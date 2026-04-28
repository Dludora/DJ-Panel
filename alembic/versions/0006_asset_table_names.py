"""rename dataset tables to asset tables

Revision ID: 0006_asset_table_names
Revises: 0005_run_submissions
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_asset_table_names"
down_revision = "0005_run_submissions"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in _tables():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _constraints(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in _tables():
        return set()
    constraints = {item["name"] for item in inspector.get_unique_constraints(table_name)}
    pk = inspector.get_pk_constraint(table_name).get("name")
    if pk:
        constraints.add(pk)
    return constraints


def _rename_constraint(table_name: str, old_name: str, new_name: str) -> None:
    if old_name in _constraints(table_name) and new_name not in _constraints(table_name):
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )
        )


def _rename_index(table_name: str, old_name: str, new_name: str) -> None:
    if old_name in _indexes(table_name) and new_name not in _indexes(table_name):
        op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def upgrade() -> None:
    tables = _tables()
    if "datasets" in tables and "assets" not in tables:
        op.rename_table("datasets", "assets")
    if "dataset_versions" in tables and "asset_versions" not in tables:
        op.rename_table("dataset_versions", "asset_versions")
    if "dataset_facets" in tables and "asset_facets" not in tables:
        op.rename_table("dataset_facets", "asset_facets")

    _rename_constraint("assets", "uq_datasets_namespace_name", "uq_assets_namespace_name")
    _rename_constraint(
        "asset_versions",
        "uq_dataset_versions_dataset_version",
        "uq_asset_versions_asset_version",
    )
    _rename_constraint(
        "asset_facets",
        "uq_dataset_facets_dataset_name",
        "uq_asset_facets_asset_name",
    )
    _rename_index("asset_versions", "ix_dataset_versions_dataset", "ix_asset_versions_asset")
    _rename_index("job_version_io_mapping", "ix_job_version_io_dataset", "ix_job_version_io_asset")


def downgrade() -> None:
    _rename_index("job_version_io_mapping", "ix_job_version_io_asset", "ix_job_version_io_dataset")
    _rename_index("asset_versions", "ix_asset_versions_asset", "ix_dataset_versions_dataset")
    _rename_constraint(
        "asset_facets",
        "uq_asset_facets_asset_name",
        "uq_dataset_facets_dataset_name",
    )
    _rename_constraint(
        "asset_versions",
        "uq_asset_versions_asset_version",
        "uq_dataset_versions_dataset_version",
    )
    _rename_constraint("assets", "uq_assets_namespace_name", "uq_datasets_namespace_name")

    tables = _tables()
    if "asset_facets" in tables and "dataset_facets" not in tables:
        op.rename_table("asset_facets", "dataset_facets")
    if "asset_versions" in tables and "dataset_versions" not in tables:
        op.rename_table("asset_versions", "dataset_versions")
    if "assets" in tables and "datasets" not in tables:
        op.rename_table("assets", "datasets")
