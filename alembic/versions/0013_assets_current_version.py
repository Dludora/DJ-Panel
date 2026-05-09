"""add current version pointer to assets

Revision ID: 0013_assets_current_version
Revises: 0012_task_artifact_asset_names
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_assets_current_version"
down_revision = "0012_task_artifact_asset_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column("current_version_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_assets_current_version_id",
            "asset_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE assets AS a
                SET current_version_id = av.id
                FROM (
                    SELECT DISTINCT ON (asset_id) asset_id, id
                    FROM asset_versions
                    ORDER BY asset_id, created_at DESC, id DESC
                ) AS av
                WHERE a.id = av.asset_id
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                UPDATE assets
                SET current_version_id = (
                    SELECT av.id
                    FROM asset_versions AS av
                    WHERE av.asset_id = assets.id
                    ORDER BY av.created_at DESC, av.id DESC
                    LIMIT 1
                )
                """
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_constraint("fk_assets_current_version_id", type_="foreignkey")
        batch_op.drop_column("current_version_id")
