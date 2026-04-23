from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
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


datasets = Table(
    "datasets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("namespace", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("namespace", "name", name="uq_datasets_namespace_name"),
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
        "dataset_id",
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
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
        "dataset_id",
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

dataset_versions = Table(
    "dataset_versions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "dataset_id",
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("version", String(128), nullable=False),
    Column(
        "created_by_run_id",
        String(36),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("fields", json_type, nullable=False),
    Column("facets", json_type, nullable=False),
    Column("lifecycle_state", String(64), nullable=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint(
        "dataset_id", "version", name="uq_dataset_versions_dataset_version"
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
        "dataset_id",
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("io_type", String(16), nullable=False),
    UniqueConstraint(
        "job_version_id", "dataset_id", "io_type", name="uq_job_version_dataset_iotype"
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

dataset_facets = Table(
    "dataset_facets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "dataset_id",
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("facet_name", String(255), nullable=False),
    Column("payload", json_type, nullable=False),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("dataset_id", "facet_name", name="uq_dataset_facets_dataset_name"),
)

Index("ix_lineage_events_run_id", lineage_events.c.run_id)
Index("ix_lineage_events_created_at", lineage_events.c.created_at)
Index("ix_job_versions_current", job_versions.c.job_id, job_versions.c.is_current)
Index("ix_job_version_io_dataset", job_version_io_mapping.c.dataset_id)
Index("ix_runs_job_id", runs.c.job_id)
Index(
    "ix_dataset_versions_dataset",
    dataset_versions.c.dataset_id,
    dataset_versions.c.created_at,
)
