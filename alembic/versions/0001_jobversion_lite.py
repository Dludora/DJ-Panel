"""initial jobversion lite schema"""

from alembic import op
import sqlalchemy as sa

revision = '0001_jobversion_lite'
down_revision = None
branch_labels = None
depends_on = None


json_type = sa.JSON()


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('current_job_version_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('namespace', 'name', name='uq_jobs_namespace_name'),
    )
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('namespace', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('namespace', 'name', name='uq_datasets_namespace_name'),
    )
    op.create_table(
        'job_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_hash', sa.String(length=128), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('job_id', 'version_hash', name='uq_job_versions_job_hash'),
    )
    op.create_table(
        'runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=255), nullable=False),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.String(length=64), nullable=True),
        sa.Column('job_version_id', sa.String(length=36), sa.ForeignKey('job_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('run_id', name='uq_runs_run_id'),
    )
    op.create_table(
        'lineage_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('job_namespace', sa.String(length=255), nullable=True),
        sa.Column('job_name', sa.String(length=255), nullable=True),
        sa.Column('run_id', sa.String(length=255), nullable=True),
        sa.Column('producer', sa.Text(), nullable=True),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'run_inputs',
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'run_outputs',
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'job_version_io_mapping',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_version_id', sa.String(length=36), sa.ForeignKey('job_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('io_type', sa.String(length=16), nullable=False),
        sa.UniqueConstraint('job_version_id', 'dataset_id', 'io_type', name='uq_job_version_dataset_iotype'),
    )
    op.create_table(
        'run_facets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('facet_name', sa.String(length=255), nullable=False),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('run_id', 'facet_name', name='uq_run_facets_run_name'),
    )
    op.create_table(
        'job_facets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('facet_name', sa.String(length=255), nullable=False),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('job_id', 'facet_name', name='uq_job_facets_job_name'),
    )
    op.create_table(
        'dataset_facets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_id', sa.String(length=36), sa.ForeignKey('datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('facet_name', sa.String(length=255), nullable=False),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dataset_id', 'facet_name', name='uq_dataset_facets_dataset_name'),
    )
    op.create_index('ix_lineage_events_run_id', 'lineage_events', ['run_id'])
    op.create_index('ix_lineage_events_created_at', 'lineage_events', ['created_at'])
    op.create_index('ix_job_versions_current', 'job_versions', ['job_id', 'is_current'])
    op.create_index('ix_job_version_io_dataset', 'job_version_io_mapping', ['dataset_id'])
    op.create_index('ix_runs_job_id', 'runs', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_runs_job_id', table_name='runs')
    op.drop_index('ix_job_version_io_dataset', table_name='job_version_io_mapping')
    op.drop_index('ix_job_versions_current', table_name='job_versions')
    op.drop_index('ix_lineage_events_created_at', table_name='lineage_events')
    op.drop_index('ix_lineage_events_run_id', table_name='lineage_events')
    op.drop_table('dataset_facets')
    op.drop_table('job_facets')
    op.drop_table('run_facets')
    op.drop_table('job_version_io_mapping')
    op.drop_table('run_outputs')
    op.drop_table('run_inputs')
    op.drop_table('lineage_events')
    op.drop_table('runs')
    op.drop_table('job_versions')
    op.drop_table('datasets')
    op.drop_table('jobs')
