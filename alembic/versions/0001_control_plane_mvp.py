"""control plane MVP schema

Revision ID: 0001_control_plane_mvp
Revises: 
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0001_control_plane_mvp'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('slug', sa.String(length=120), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'workspace_members',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=64), nullable=False, server_default='MEMBER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workspace_id', 'user_name', name='uq_workspace_members_workspace_user'),
    )
    op.create_table(
        'recipes',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('owner_name', sa.String(length=255), nullable=False),
        sa.Column('current_version_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_recipes_workspace_name'),
    )
    op.create_table(
        'recipe_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('recipe_id', sa.String(length=36), sa.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('recipe_body', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('script_path', sa.Text(), nullable=False),
        sa.Column('parameter_schema', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('env_template', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('execution_spec', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('lineage_namespace', sa.Text(), nullable=True),
        sa.Column('lineage_job_name', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('recipe_id', 'version_number', name='uq_recipe_versions_recipe_version_number'),
    )
    op.create_table(
        'recipe_runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipe_id', sa.String(length=36), sa.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipe_version_id', sa.String(length=36), sa.ForeignKey('recipe_versions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('requested_by', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('root_lineage_node_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )
    op.create_table(
        'workers',
        sa.Column('id', sa.String(length=255), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('labels', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('capabilities', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('max_concurrency', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('worker_id', sa.String(length=255), sa.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('labels', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('capabilities', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipe_run_id', sa.String(length=36), sa.ForeignKey('recipe_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipe_version_id', sa.String(length=36), sa.ForeignKey('recipe_versions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('assigned_worker_id', sa.String(length=255), sa.ForeignKey('workers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('current_attempt_id', sa.String(length=36), nullable=True),
        sa.Column('lease_token', sa.String(length=64), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('script_path', sa.Text(), nullable=False),
        sa.Column('env_vars', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('execution_spec', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )
    op.create_table(
        'task_attempts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('task_id', sa.String(length=36), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('worker_id', sa.String(length=255), sa.ForeignKey('workers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('lease_token', sa.String(length=64), nullable=False),
        sa.Column('openlineage_run_id', sa.String(length=255), nullable=True),
        sa.Column('mlflow_run_id', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('task_id', 'attempt_number', name='uq_task_attempts_task_attempt_number'),
    )
    op.create_table(
        'task_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('attempt_id', sa.String(length=36), sa.ForeignKey('task_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stream', sa.String(length=32), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('logged_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'task_artifacts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('attempt_id', sa.String(length=36), sa.ForeignKey('task_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('uri', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('dataset_id', sa.String(length=255), nullable=True),
        sa.Column('dataset_version_id', sa.String(length=255), nullable=True),
        sa.Column('model_uri', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('task_artifacts')
    op.drop_table('task_logs')
    op.drop_table('task_attempts')
    op.drop_table('tasks')
    op.drop_table('worker_heartbeats')
    op.drop_table('workers')
    op.drop_table('recipe_runs')
    op.drop_table('recipe_versions')
    op.drop_table('recipes')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
