"""add run and asset-version links to asset facets

Revision ID: 0015_asset_facets_version_links
Revises: 0014_job_facets_version_links
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_asset_facets_version_links"
down_revision = "0014_job_facets_version_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    with op.batch_alter_table("asset_facets") as batch_op:
        batch_op.add_column(
            sa.Column("asset_version_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("run_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_asset_facets_asset_version_id",
            "asset_versions",
            ["asset_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_asset_facets_run_id",
            "runs",
            ["run_id"],
            ["id"],
            ondelete="CASCADE",
        )
        if dialect_name != "sqlite":
            batch_op.drop_constraint("uq_asset_facets_asset_name", type_="unique")

    op.create_index("ix_asset_facets_asset", "asset_facets", ["asset_id"], unique=False)
    op.create_index(
        "ix_asset_facets_asset_version",
        "asset_facets",
        ["asset_version_id"],
        unique=False,
    )
    op.create_index("ix_asset_facets_run", "asset_facets", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_asset_facets_run", table_name="asset_facets")
    op.drop_index("ix_asset_facets_asset_version", table_name="asset_facets")
    op.drop_index("ix_asset_facets_asset", table_name="asset_facets")

    with op.batch_alter_table("asset_facets") as batch_op:
        batch_op.create_unique_constraint(
            "uq_asset_facets_asset_name", ["asset_id", "facet_name"]
        )
        batch_op.drop_constraint("fk_asset_facets_run_id", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_asset_facets_asset_version_id", type_="foreignkey"
        )
        batch_op.drop_column("run_id")
        batch_op.drop_column("asset_version_id")
