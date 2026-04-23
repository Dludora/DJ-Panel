# DJ Lineage Backend Architecture Guide for Agents

This file is a maintenance-oriented map of the Python lineage backend under `standalone/dj-lineage-backend/`.

It is intended to help future contributors make safe changes without having to rediscover the ingestion, projection, and Marquez-compatibility flows from scratch.

Keep this file current whenever any of the following change:

- OpenLineage ingestion entrypoints or event typing
- database schema or Alembic migrations
- job version or dataset version projection behavior
- lineage graph response shape
- metadata endpoints used by the Marquez web app

## Scope and design intent

This service is a Python lineage backend for DJ Panel, implemented with:

- FastAPI
- SQLAlchemy Core
- Alembic
- PostgreSQL

The current backend is intentionally a `JobVersion Lite` implementation:

- it accepts OpenLineage-compatible events
- stores raw event payloads
- projects table-level lineage into relational tables
- computes a stable `job_version` on `COMPLETE`
- snapshots output `dataset_versions` on `COMPLETE`
- exposes a Marquez-friendly table-level graph and metadata API surface

The current backend does not yet implement:

- column-level lineage
- streaming-specific version semantics
- complex backfill or replay reconciliation
- fine-grained job version diffs
- search, tags, delete endpoints, or dashboard metric aggregation

## Repository layout

- `app/main.py`
  - FastAPI application entrypoint
- `app/api/routes/`
  - HTTP route layer
- `app/models/`
  - Pydantic request and response models
- `app/services/`
  - orchestration layer
- `app/repositories/`
  - SQLAlchemy Core persistence and query logic
- `app/db/`
  - shared schema and engine wiring
- `alembic/`
  - schema migrations
- `tests/`
  - smoke, ingestion, and compatibility tests

Ignore local development artifacts such as `.venv/`, `.pytest_cache/`, and `*.egg-info/` when making code changes.

## Runtime architecture

At a high level, the runtime flow is:

1. OpenLineage event arrives at `POST /api/v1/lineage`.
2. The payload is classified and validated into `RunEvent`, `JobEvent`, or `DatasetEvent`.
3. The raw payload is stored in `lineage_events`.
4. The event is projected into namespaces, jobs, runs, datasets, facets, mappings, `job_versions`, and `dataset_versions`.
5. The UI calls lineage and metadata endpoints.
6. The backend returns Marquez-friendly graph nodes, jobs, datasets, runs, versions, and facets.

## Core entrypoints

### Application bootstrap

- `app/main.py`
  - creates the FastAPI app
  - mounts the health, lineage, and metadata routers

### Route modules

- `app/api/routes/health.py`
  - `GET /health`
- `app/api/routes/lineage.py`
  - `POST /api/v1/lineage`
  - `GET /api/v1/lineage`
  - `GET /api/v1/events/lineage`
- `app/api/routes/metadata.py`
  - `GET /api/v1/namespaces`
  - `GET /api/v1/jobs`
  - `GET /api/v1/namespaces/{namespace}/jobs`
  - `GET /api/v1/namespaces/{namespace}/jobs/{job_name}`
  - `GET /api/v1/namespaces/{namespace}/jobs/{job_name}/runs`
  - `GET /api/v1/namespaces/{namespace}/datasets`
  - `GET /api/v1/namespaces/{namespace}/datasets/{dataset_name}`
  - `GET /api/v1/namespaces/{namespace}/datasets/{dataset_name}/versions`
  - `GET /api/v1/jobs/runs/{run_id}/facets?type=run|job`

## Module responsibilities

### `app/models/`

- `app/models/openlineage.py`
  - permissive Pydantic models for incoming events
  - `RunEvent`, `JobEvent`, `DatasetEvent`, `RunRef`, `JobRef`, `DatasetRef`
  - handles OpenLineage-style aliases such as `schemaURL`, `eventType`, `eventTime`, `runId`, `inputFacets`, `outputFacets`
- `app/models/api.py`
  - small API response models such as lineage ingestion acknowledgements
- `app/models/db_rows.py`
  - typed row objects for write-side persistence results
  - used by `ProjectionRepository` instead of returning untyped dictionaries
- `app/models/metadata_api.py`
  - typed read-side models for metadata and Marquez-compatible API payloads
  - used by `MetadataRepository`, then serialized at the service boundary
- `app/models/lineage_enums.py`
  - shared enums for run states, IO direction, dataset lifecycle state, and web-facing run status mapping
- `app/models/graph.py`
  - response model for table-level lineage
  - defines `Edge`, `Node`, and `LineageResponse`

### `app/services/`

- `app/services/event_resolver.py`
  - mirrors Marquez's `schemaURL`-based event typing approach first
  - falls back to payload shape when `schemaURL` is missing or only points at the root schema
  - parses the payload into `RunEvent`, `JobEvent`, or `DatasetEvent`
- `app/services/ingestion.py`
  - main write orchestration layer
  - stores raw events
  - projects `DatasetEvent` into namespaces, datasets, and dataset facets
  - projects `JobEvent` into namespaces, jobs, datasets, and job/dataset facets
  - projects `RunEvent` into namespaces, jobs, runs, datasets, facets, input/output mappings
  - creates `job_versions` on `RunEvent.COMPLETE`
  - creates output `dataset_versions` on `RunEvent.COMPLETE`
- `app/services/lineage_query.py`
  - main table-level graph assembly logic
  - traverses current `job_versions`
  - returns Marquez-friendly `graph` payloads
- `app/services/metadata.py`
  - read-side orchestration for namespaces, jobs, runs, datasets, versions, and facets

### `app/repositories/`

- `app/repositories/lineage_events.py`
  - raw event inserts and recent raw event listing
- `app/repositories/projection.py`
  - write-side projection logic
  - upserts namespaces, jobs, runs, datasets
  - stores facets
  - maintains `run_inputs` and `run_outputs`
  - computes version hashes
  - creates or updates `job_versions`
  - creates output `dataset_versions`
  - returns typed row objects that correspond to write-side tables rather than plain dicts
- `app/repositories/lineage_query.py`
  - lower-level lineage traversal helpers
  - reads current `job_versions`
  - resolves upstream and downstream dataset/job relationships
- `app/repositories/metadata.py`
  - read-side materialization into Marquez-style API shapes
  - builds job, dataset, run, namespace, and dataset-version typed models
  - powers list and detail endpoints

### `app/db/`

- `app/db/schema.py`
  - SQLAlchemy Core table definitions
- `app/db/session.py`
  - shared engine factory

## Persistence model

### Raw event store

- `lineage_events`
  - stores original event payloads and identifying metadata

### Canonical metadata tables

- `namespaces`
- `jobs`
- `runs`
- `datasets`
- `dataset_versions`
- `job_versions`
- `job_version_io_mapping`
- `run_inputs`
- `run_outputs`
- `run_facets`
- `job_facets`
- `dataset_facets`

### Schema files

- `app/db/schema.py`
- `alembic/versions/0001_jobversion_lite.py`
- `alembic/versions/0002_metadata_compat.py`

## Ingestion path

For the main write path, start reading in this order:

1. `app/api/routes/lineage.py`
2. `app/models/openlineage.py`
3. `app/services/event_resolver.py`
4. `app/services/ingestion.py`
5. `app/repositories/lineage_events.py`
6. `app/repositories/projection.py`
7. `app/db/schema.py`

Important write-side behaviors:

- every event is persisted to `lineage_events`
- `DatasetEvent` and `JobEvent` are accepted and partially projected as static metadata updates
- only `RunEvent` advances run state and table-level lineage mappings
- runs keep their real input and output dataset mappings
- only `RunEvent.COMPLETE` advances the current `job_version`
- only `RunEvent` output datasets receive `dataset_versions`

## Lineage query path

For the table-level graph path, read in this order:

1. `app/api/routes/lineage.py`
2. `app/services/lineage_query.py`
3. `app/repositories/lineage_query.py`
4. `app/repositories/metadata.py`
5. `app/models/graph.py`

Important query-side behavior:

- `nodeId` must look like `job:namespace:name` or `dataset:namespace:name`
- graph traversal is based on the current `job_version`
- the response shape is intentionally close to Marquez web expectations

## Metadata query path

For job, dataset, run, namespace, and facet reads, start here:

1. `app/api/routes/metadata.py`
2. `app/services/metadata.py`
3. `app/repositories/metadata.py`

This path is what powers the current Marquez-web compatibility layer for:

- namespaces
- jobs list and job detail
- runs list
- datasets list and dataset detail
- dataset versions
- run and job facets

## Tests

- `tests/test_smoke.py`
  - event model resolution and payload parsing smoke coverage
- `tests/test_ingestion_flow.py`
  - `START -> COMPLETE` lifecycle
  - `job_versions` creation
  - facets projection
  - namespace and dataset version persistence
  - `JobEvent` / `DatasetEvent` acceptance and partial projection
- `tests/test_api_compat.py`
  - Marquez-friendly response shape for graph and metadata endpoints
  - static job and dataset event acceptance through HTTP

Fixtures live under:

- `tests/fixtures/run_start.json`
- `tests/fixtures/run_complete.json`
- `tests/fixtures/dataset_event.json`
- `tests/fixtures/job_event.json`

## Common change patterns

### If you change event ingestion

Inspect and usually update:

- `app/models/openlineage.py`
- `app/services/event_resolver.py`
- `app/services/ingestion.py`
- `app/repositories/projection.py`
- `app/repositories/lineage_events.py`
- `app/db/schema.py`
- `alembic/versions/*`
- relevant tests under `tests/`

Be careful with:

- idempotency of repeated events
- state transitions for `START`, `RUNNING`, `COMPLETE`, `FAIL`, `ABORT`
- keeping the raw event store as the source-of-truth input

### If you change job or dataset response shapes

Inspect and usually update:

- `app/repositories/metadata.py`
- `app/models/graph.py`
- `app/services/lineage_query.py`
- `tests/test_api_compat.py`

Be careful with:

- Marquez web assumptions about field names
- top-level `node.type` versus `node.data.type`
- nullable fields such as `columnLineage`, `latestRun`, and `description`

### If you change versioning behavior

Inspect and usually update:

- `app/repositories/projection.py`
- `app/repositories/lineage_query.py`
- `app/repositories/metadata.py`
- `alembic/versions/*` if schema changes
- `tests/test_ingestion_flow.py`

Be careful with:

- what counts as a new `job_version`
- what creates a new `dataset_version`
- keeping current-version lineage stable for the UI

## Suggested developer commands

- install dependencies:
  - `pip install -e '.[dev]'`
- run migrations:
  - `alembic upgrade head`
- start dev server:
  - `uvicorn app.main:app --reload`
- run tests:
  - `pytest tests/test_smoke.py tests/test_ingestion_flow.py tests/test_api_compat.py -q`

## Practical reading order for new agents

If you need to understand this backend quickly, read files in this order:

1. `app/main.py`
2. `app/api/routes/lineage.py`
3. `app/services/ingestion.py`
4. `app/repositories/projection.py`
5. `app/api/routes/metadata.py`
6. `app/services/metadata.py`
7. `app/repositories/metadata.py`
8. `app/services/lineage_query.py`
9. `app/repositories/lineage_query.py`
10. `app/db/schema.py`

That sequence follows the user-visible flow from ingest to graph and detail responses.
