from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
json_type = JSON().with_variant(JSONB, "postgresql")

workspaces = Table(
    "workspaces",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("slug", String(120), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

workspace_members = Table(
    "workspace_members",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "workspace_id",
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("user_name", String(255), nullable=False),
    Column("role", String(64), nullable=False, server_default="MEMBER"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        "workspace_id", "user_name", name="uq_workspace_members_workspace_user"
    ),
)

recipes = Table(
    "recipes",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "workspace_id",
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("owner_name", String(255), nullable=False),
    Column("current_version_id", String(36), nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("workspace_id", "name", name="uq_recipes_workspace_name"),
)

recipe_versions = Table(
    "recipe_versions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "recipe_id",
        String(36),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("version_number", Integer, nullable=False),
    Column("recipe_body", json_type, nullable=False, server_default="{}"),
    Column("command", Text, nullable=False),
    Column("script_path", Text, nullable=False),
    Column("parameter_schema", json_type, nullable=False, server_default="{}"),
    Column("env_template", json_type, nullable=False, server_default="{}"),
    Column("execution_spec", json_type, nullable=False, server_default="{}"),
    Column("timeout_seconds", Integer, nullable=False, server_default="3600"),
    Column("created_by", String(255), nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        "recipe_id", "version_number", name="uq_recipe_versions_recipe_version_number"
    ),
)

run_submissions = Table(
    "run_submissions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "workspace_id",
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "recipe_id",
        String(36),
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "recipe_version_id",
        String(36),
        ForeignKey("recipe_versions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("requested_by", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("parameters", json_type, nullable=False, server_default="{}"),
    Column("root_lineage_node_id", Text, nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column("failure_reason", Text, nullable=True),
)

workers = Table(
    "workers",
    metadata,
    Column("id", String(255), primary_key=True),
    Column(
        "workspace_id",
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("display_name", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("labels", json_type, nullable=False, server_default="{}"),
    Column("capabilities", json_type, nullable=False, server_default="{}"),
    Column("max_concurrency", Integer, nullable=False, server_default="1"),
    Column("last_heartbeat_at", DateTime(timezone=True), nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

worker_heartbeats = Table(
    "worker_heartbeats",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "worker_id",
        String(255),
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False),
    Column("labels", json_type, nullable=False, server_default="{}"),
    Column("capabilities", json_type, nullable=False, server_default="{}"),
    Column(
        "heartbeat_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
)

tasks = Table(
    "tasks",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "workspace_id",
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "run_submission_id",
        String(36),
        ForeignKey("run_submissions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "recipe_version_id",
        String(36),
        ForeignKey("recipe_versions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("task_kind", String(64), nullable=False, server_default="generic_command"),
    Column("status", String(32), nullable=False),
    Column(
        "assigned_worker_id",
        String(255),
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("current_attempt_id", String(36), nullable=True),
    Column("lease_token", String(64), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("attempt_count", Integer, nullable=False, server_default="0"),
    Column("command", Text, nullable=False),
    Column("script_path", Text, nullable=False),
    Column("env_vars", json_type, nullable=False, server_default="{}"),
    Column("execution_spec", json_type, nullable=False, server_default="{}"),
    Column("timeout_seconds", Integer, nullable=False, server_default="3600"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column("failure_reason", Text, nullable=True),
)

task_attempts = Table(
    "task_attempts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "task_id",
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "worker_id",
        String(255),
        ForeignKey("workers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("attempt_number", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("lease_token", String(64), nullable=False),
    Column("openlineage_run_id", String(255), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column("last_heartbeat_at", DateTime(timezone=True), nullable=True),
    Column("failure_reason", Text, nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        "task_id", "attempt_number", name="uq_task_attempts_task_attempt_number"
    ),
)

task_logs = Table(
    "task_logs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "attempt_id",
        String(36),
        ForeignKey("task_attempts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("stream", String(32), nullable=False),
    Column("message", Text, nullable=False),
    Column("sequence", Integer, nullable=False, server_default="0"),
    Column(
        "logged_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

task_artifacts = Table(
    "task_artifacts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "attempt_id",
        String(36),
        ForeignKey("task_attempts.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(32), nullable=False),
    Column("name", String(255), nullable=False),
    Column("uri", Text, nullable=False),
    Column("metadata_json", json_type, nullable=False, server_default="{}"),
    Column("dataset_id", String(255), nullable=True),
    Column("dataset_version_id", String(255), nullable=True),
    Column("model_uri", Text, nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

namespaces = Table(
    "namespaces",
    metadata,
    Column("name", String(255), primary_key=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column("owner_name", String(255), nullable=False, server_default=""),
    Column("description", Text, nullable=False, server_default=""),
    Column("is_hidden", Boolean, nullable=False, server_default=false()),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("namespace", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("location", Text, nullable=True),
    Column("current_job_version_id", String(36), nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("namespace", "name", name="uq_jobs_namespace_name"),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_id", String(255), nullable=False),
    Column(
        "job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("event_time", DateTime(timezone=True), nullable=True),
    Column("state", String(64), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column(
        "job_version_id",
        String(36),
        ForeignKey("job_versions.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("run_id", name="uq_runs_run_id"),
)

assets = Table(
    "assets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("namespace", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("asset_kind", String(64), nullable=False, server_default="DATASET"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("namespace", "name", name="uq_assets_namespace_name"),
)

lineage_events = Table(
    "lineage_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("event_type", String(64), nullable=False),
    Column("event_time", DateTime(timezone=True), nullable=True),
    Column("job_namespace", String(255), nullable=True),
    Column("job_name", String(255), nullable=True),
    Column("run_id", String(255), nullable=True),
    Column("producer", Text, nullable=True),
    Column("payload", json_type, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

run_inputs = Table(
    "run_inputs",
    metadata,
    Column(
        "run_id",
        String(36),
        ForeignKey("runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

run_outputs = Table(
    "run_outputs",
    metadata,
    Column(
        "run_id",
        String(36),
        ForeignKey("runs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

asset_versions = Table(
    "asset_versions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("version", String(128), nullable=False),
    Column(
        "created_by_run_id",
        String(36),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("storage_uri", Text, nullable=True),
    Column("fields", json_type, nullable=False),
    Column("facets", json_type, nullable=False),
    Column("lifecycle_state", String(64), nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        "asset_id", "version", name="uq_asset_versions_asset_version"
    ),
)

job_versions = Table(
    "job_versions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("version_hash", String(128), nullable=False),
    Column("is_current", Boolean, nullable=False, server_default=false()),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("job_id", "version_hash", name="uq_job_versions_job_hash"),
)

job_version_io_mapping = Table(
    "job_version_io_mapping",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "job_version_id",
        String(36),
        ForeignKey("job_versions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("io_type", String(16), nullable=False),
    UniqueConstraint(
        "job_version_id", "asset_id", "io_type", name="uq_job_version_asset_iotype"
    ),
)

run_facets = Table(
    "run_facets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "run_id", String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("facet_name", String(255), nullable=False),
    Column("payload", json_type, nullable=False),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("run_id", "facet_name", name="uq_run_facets_run_name"),
)

job_facets = Table(
    "job_facets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("facet_name", String(255), nullable=False),
    Column("payload", json_type, nullable=False),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("job_id", "facet_name", name="uq_job_facets_job_name"),
)

asset_facets = Table(
    "asset_facets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("facet_name", String(255), nullable=False),
    Column("payload", json_type, nullable=False),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("asset_id", "facet_name", name="uq_asset_facets_asset_name"),
)

Index("ix_lineage_events_run_id", lineage_events.c.run_id)
Index("ix_lineage_events_created_at", lineage_events.c.created_at)
Index("ix_job_versions_current", job_versions.c.job_id, job_versions.c.is_current)
Index("ix_job_version_io_asset", job_version_io_mapping.c.asset_id)
Index("ix_runs_job_id", runs.c.job_id)
Index(
    "ix_asset_versions_asset",
    asset_versions.c.asset_id,
    asset_versions.c.created_at,
)

# Compatibility aliases for OpenLineage dataset-shaped APIs and existing tests.
datasets = assets
dataset_versions = asset_versions
dataset_facets = asset_facets
