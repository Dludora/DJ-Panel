"""add run and job-version links to job facets

Revision ID: 0014_job_facets_version_links
Revises: 0013_assets_current_version
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_job_facets_version_links"
down_revision = "0013_assets_current_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("job_facets") as batch_op:
        batch_op.add_column(
            sa.Column("job_version_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("run_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_job_facets_job_version_id",
            "job_versions",
            ["job_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_job_facets_run_id",
            "runs",
            ["run_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint("uq_job_facets_job_name", type_="unique")

    op.create_index("ix_job_facets_job", "job_facets", ["job_id"], unique=False)
    op.create_index(
        "ix_job_facets_job_version", "job_facets", ["job_version_id"], unique=False
    )
    op.create_index("ix_job_facets_run", "job_facets", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_facets_run", table_name="job_facets")
    op.drop_index("ix_job_facets_job_version", table_name="job_facets")
    op.drop_index("ix_job_facets_job", table_name="job_facets")

    with op.batch_alter_table("job_facets") as batch_op:
        batch_op.create_unique_constraint(
            "uq_job_facets_job_name", ["job_id", "facet_name"]
        )
        batch_op.drop_constraint("fk_job_facets_run_id", type_="foreignkey")
        batch_op.drop_constraint("fk_job_facets_job_version_id", type_="foreignkey")
        batch_op.drop_column("run_id")
        batch_op.drop_column("job_version_id")
