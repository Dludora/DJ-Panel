# DJ Panel Backend Guide for Agents

This module is the backend for DJ Panel.
It combines:

- a control-plane service for workspace, recipe, run, task, and worker orchestration
- a lineage and metadata service for OpenLineage ingestion, lineage graph traversal, and Marquez-style metadata queries

The default local database target is PostgreSQL.

## Primary responsibilities

- manage workspaces and versioned DataJuicer recipes
- create recipe runs and expand each run into one claimable task
- register workers and record heartbeats
- let workers claim tasks atomically
- track task attempts, logs, artifacts, and lineage references
- ingest OpenLineage-compatible events
- project lineage data into jobs, runs, datasets, versions, and facets
- expose metadata and lineage graph query endpoints

## Canonical planning docs

When making implementation changes, prefer the following documents as the current source of planning truth:

- `TARGET_ARCHITECTURE.md`
- `DJ_PROCESSING_V1_DESIGN.md`
- `DATABASE_SCHEMA_DRAFT.md`
- `V1_API_OPENAPI_STYLE.md`
- `DJ_WORKER_PAYLOAD_AND_SEQUENCE.md`

Older overlapping drafts such as `BACKEND_FUNCTION_MAP.md` and `V1_API_DRAFT.md` have been removed on purpose.

## Layout

- `app/main.py`: FastAPI entrypoint
- `app/api/routes/`: HTTP routes by domain (`health`, `lineage`, `metadata`, `workspaces`, `recipes`, `runs`, `workers`, `tasks`)
- `app/models/`: request and response models, DB row models, shared enums, OpenLineage models
- `app/repositories/`: SQLAlchemy Core persistence by domain
- `app/services/`: orchestration layer that combines repositories into API behavior
- `app/db/schema.py`: canonical merged table definitions for control-plane plus lineage and metadata
- `alembic/versions/`: schema history for both the control-plane branch and the lineage and metadata branch, plus a merge head
- `tools/worker_client.py`: minimal worker client for local/ECS/DSW style execution

## Current scope

This module currently exposes one merged FastAPI app with both execution orchestration and lineage metadata capabilities.

Included:

- workspace CRUD-lite (create/list)
- recipe create/list/detail and versioning
- recipe-run create/list/detail
- task list/detail, claim, start, complete, fail, cancel
- worker register/list/heartbeat
- task logs and artifact references
- fields for OpenLineage and MLflow run linkage
- OpenLineage event ingestion
- raw lineage event storage
- metadata endpoints for namespaces, jobs, runs, datasets, dataset versions, and facets
- lineage graph queries over current job-version topology

Not yet included:

- retries and stale-lease recovery
- queue priority
- step-level DAG scheduling
- fine-grained RBAC
- artifact binary storage
- automatic propagation from control-plane task transitions into lineage projection tables
- persistent tag storage behind the tag endpoints

## Design notes

- task granularity is recipe-run level in v1
- recipes are the source of truth in Panel
- workers execute local scripts/commands that already exist in their environment
- claim is pull-based and atomic at the database write level
- workspace is the main isolation boundary
- lineage projection is event-driven and independent from task state transitions
- the merged schema uses PostgreSQL-first JSON handling through `JSONB` variants
- the default local connection string is `postgresql+psycopg:///dj_panel`
