"""add metadata compatibility tables

Revision ID: 0002_metadata_compat
Revises: 0001_jobversion_lite
Create Date: 2026-04-23 22:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002_metadata_compat'
down_revision = '0001_jobversion_lite'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'namespaces',
        sa.Column('name', sa.String(length=255), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('owner_name', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column('datasets', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column('runs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('runs', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.String(length=128), nullable=False),
        sa.Column('created_by_run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('facets', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('lifecycle_state', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_id', 'version', name='uq_dataset_versions_dataset_version'),
    )
    op.create_index('ix_dataset_versions_dataset', 'dataset_versions', ['dataset_id', 'created_at'])

    op.execute(
        """
        INSERT INTO namespaces (name, created_at, updated_at, owner_name, description, is_hidden)
        SELECT DISTINCT namespace, NOW(), NOW(), '', '', FALSE FROM jobs
        UNION
        SELECT DISTINCT namespace, NOW(), NOW(), '', '', FALSE FROM datasets
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index('ix_dataset_versions_dataset', table_name='dataset_versions')
    op.drop_table('dataset_versions')
    op.drop_column('runs', 'ended_at')
    op.drop_column('runs', 'started_at')
    op.drop_column('datasets', 'updated_at')
    op.drop_table('namespaces')
