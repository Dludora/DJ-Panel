# DJ Panel Backend Guide for Agents

This module is the backend for DJ Panel.
It combines:

- a control-plane service for workspace, recipe, run, task, and worker orchestration
- an asset catalog and lineage service for OpenLineage ingestion, projection, and graph traversal

The default local database target is PostgreSQL.

## Primary responsibilities

- manage workspaces and versioned DataJuicer recipes
- create run submissions and expand each submission into one claimable task
- register workers and record heartbeats
- let workers claim tasks atomically
- track task attempts, registered log files, artifacts, and lineage references
- ingest OpenLineage-compatible events
- project lineage data into jobs, runs, assets, versions, and facets
- expose asset catalog and lineage graph query endpoints

## Canonical docs

Start with:

- `docs/README.md`
- `docs/CURRENT_PROJECT.md`

Then use the focused design documents in `docs/`:

- `docs/TARGET_ARCHITECTURE.md`
- `docs/DJ_PROCESSING_V1_DESIGN.md`
- `docs/DATABASE_SCHEMA_DRAFT.md`
- `docs/V1_API_OPENAPI_STYLE.md`
- `docs/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md`

## Layout

- `app/main.py`: FastAPI entrypoint
- `app/api/routes/`: HTTP routes by domain (`lineage`, `assets`, `workspaces`, `recipes`, `run_submissions`, `workers`, `tasks`)
- `app/models/api.py`: Pydantic request and response DTOs
- `app/models/protocols/`: external protocol schemas such as OpenLineage
- `app/models/constant.py`: shared enums and constant mappings
- `app/db/rows.py`: typed row mirrors for tables defined in `app/db/schema.py`
- `app/repositories/`: SQLAlchemy Core persistence by domain
- `app/services/`: orchestration layer that combines repositories into API behavior
- `app/db/schema.py`: canonical merged table definitions for control-plane, asset catalog, and lineage projection
- `alembic/versions/`: schema history for the control-plane, asset catalog, and lineage projection model
- `cli/`: `dj-panel` command-line interface, including workspace/recipe/run commands and the DJ worker runtime

## Current scope

This module currently exposes one merged FastAPI app with both execution orchestration and asset-catalog/lineage capabilities.

Included:

- workspace CRUD-lite (create/list)
- recipe create/list/detail and versioning
- run-submission create/list/detail
- task list/detail, claim, start, complete, fail, cancel
- worker register/list/heartbeat
- execution log file artifacts and other artifact references
- fields for OpenLineage and MLflow run linkage
- OpenLineage event ingestion
- raw lineage event storage
- asset catalog endpoints plus lineage browse endpoints for namespaces, jobs, runs, assets, asset versions, and facets
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

- task granularity is run-submission level in v1
- recipes are the source of truth in Panel
- workers execute local scripts/commands that already exist in their environment
- claim is pull-based and atomic at the database write level
- workspace is the main isolation boundary
- lineage projection is event-driven and independent from task state transitions, with `execution_links` bridging task attempts to observed runs/jobs
- the merged schema uses cross-dialect `SQLAlchemy JSON`
- the default local connection string is `postgresql+psycopg:///dj_panel`
