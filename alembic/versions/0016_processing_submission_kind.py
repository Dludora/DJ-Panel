"""rename processing submission kind

Revision ID: 0016_processing_submission_kind
Revises: 0015_asset_facets_version_links
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_processing_submission_kind"
down_revision = "0015_asset_facets_version_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE run_submissions SET submission_kind = 'processing' "
        "WHERE submission_kind = 'processing_pipeline'"
    )
    with op.batch_alter_table("run_submissions") as batch_op:
        batch_op.alter_column(
            "submission_kind",
            existing_type=sa.String(length=64),
            server_default="processing",
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE run_submissions SET submission_kind = 'processing_pipeline' "
        "WHERE submission_kind = 'processing'"
    )
    with op.batch_alter_table("run_submissions") as batch_op:
        batch_op.alter_column(
            "submission_kind",
            existing_type=sa.String(length=64),
            server_default="processing_pipeline",
            existing_nullable=False,
        )
