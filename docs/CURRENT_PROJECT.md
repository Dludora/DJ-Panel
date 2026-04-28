# Current Project

This document describes the current state of `dj-panel-backend`.

It is the best single-file overview for the project as it exists today.

## 1. What This Backend Is

`dj-panel-backend` is the backend for an internal team tool centered on:

- Data-Juicer recipe management and execution
- OpenLineage ingestion and projection
- team-facing orchestration of recipe submissions and workers

Today, the implemented backend is a merged FastAPI service with two connected parts:

- a control-plane for workspaces, recipes, submissions, tasks, and workers
- a lineage and metadata service for OpenLineage ingestion, lineage graph traversal, and dataset/job/run queries

## 2. Current Product Scope

The practical product scope right now is:

- Data-Juicer recipe authoring and versioning
- processing submission creation
- DJ worker polling and execution
- task logs and task artifact references
- lineage event ingestion from Data-Juicer and MLflow-style producers
- metadata queries over projected jobs, runs, datasets, dataset versions, and facets

The backend is already opinionated toward the DJ-only V1 path.

## 3. Core Mental Model

The current project uses these concepts:

- `Workspace`
  Team boundary for recipes, workers, submissions, and tasks.
- `Recipe`
  Human-facing logical Data-Juicer recipe identity.
- `RecipeVersion`
  Immutable snapshot of one recipe version.
- `RunSubmission`
  Tool-side request created by a user to execute one recipe version.
- `Task`
  Claimable dispatch unit created from one submission.
- `TaskAttempt`
  One concrete worker execution attempt.
- `Job`
  OpenLineage logical definition.
- `Run`
  OpenLineage observed runtime fact.
- `Dataset`
  Lineage-derived asset identity.
- `DatasetVersion`
  Versioned lineage-derived asset instance.

In short:

- submission is user intent
- task is dispatch
- run is observed lineage fact

## 4. Current Implementation Status

Implemented:

- `dj-panel master`
- `dj-panel workspace create`
- `dj-panel workspace list`
- `dj-panel workspace members add`
- `dj-panel workspace members list`
- `dj-panel recipe import`
- `dj-panel recipe list`
- `dj-panel recipe show`
- `dj-panel recipe publish`
- `dj-panel run submit`
- `dj-panel worker dj`

Implemented HTTP groups:

- health
- lineage ingestion and raw lineage event listing
- metadata queries
- workspaces and workspace members
- recipes and recipe versions
- run submissions
- workers
- tasks
- task logs
- task artifacts

Implemented database direction:

- PostgreSQL is the primary target
- SQLite still works for tests and lightweight local usage, but is not the primary team target

## 5. Current API Surface

Broadly, the backend exposes:

- `POST /api/v1/lineage`
- `GET /api/v1/lineage`
- `GET /api/v1/events/lineage`
- metadata endpoints under `/api/v1/namespaces`, `/api/v1/jobs`, `/api/v1/datasets`
- workspace endpoints under `/api/v1/workspaces`
- recipe endpoints under `/api/v1/workspaces/{workspace}/recipes` and `/api/v1/recipes/{id}`
- run submission endpoints under `/api/v1/workspaces/{workspace}/run-submissions`
- worker endpoints under `/api/v1/workspaces/{workspace}/workers` and `/api/v1/workers/{id}/heartbeat`
- task endpoints under `/api/v1/workspaces/{workspace}/tasks` and `/api/v1/tasks/{id}/...`

The request and response style is now intentionally camelCase at the API boundary.

## 6. Current Worker Behavior

The current worker model is DJ-specific:

```bash
dj-panel worker dj \
  --workspace llm-team \
  --worker-id dj-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-panel-worker \
  --dj-bin dj-process \
  --poll-interval 5
```

Current behavior:

- worker registers itself
- worker heartbeats
- worker only claims `taskKind = dj_recipe`
- worker materializes `recipe.yaml` locally
- worker runs `dj-process --config <materialized recipe>`
- worker streams stdout/stderr to task logs
- worker records the materialized config as a task artifact
- worker marks task success or failure

## 7. Current CLI Usage

Start backend:

```bash
dj-panel master --migrate --reload
```

Create workspace:

```bash
dj-panel workspace create llm-team --owner alice
```

Import recipe:

```bash
dj-panel recipe import ./recipe.yaml \
  --workspace llm-team \
  --name lineage_base \
  --owner alice
```

Publish new recipe version:

```bash
dj-panel recipe publish ./recipe.yaml \
  --workspace llm-team \
  --recipe lineage_base
```

Submit run:

```bash
dj-panel run submit \
  --workspace llm-team \
  --recipe lineage_base \
  --requested-by alice
```

Run DJ worker:

```bash
dj-panel worker dj \
  --workspace llm-team \
  --worker-id dj-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-panel-worker \
  --dj-bin dj-process \
  --poll-interval 5
```

## 8. Current Documentation Boundaries

Use these documents according to purpose:

- [README.md](../README.md)
  Quick start and common CLI usage.
- [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md)
  Long-term architecture.
- [DJ_PROCESSING_V1_DESIGN.md](./DJ_PROCESSING_V1_DESIGN.md)
  V1 product design.
- [V1_API_OPENAPI_STYLE.md](./V1_API_OPENAPI_STYLE.md)
  API contract target.
- [DATABASE_SCHEMA_DRAFT.md](./DATABASE_SCHEMA_DRAFT.md)
  Schema ownership and table boundaries.
- [DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)
  Worker claim payload and execution sequence.

## 9. Known Gaps

Not fully implemented yet:

- declared run-submission inputs and outputs are not yet persisted as their own first-class tables
- no retry orchestration or stale lease recovery
- no queue priority model
- no fine-grained auth or RBAC enforcement
- no binary artifact storage service
- no full workstation UI yet in this backend module
- no dedicated training/evaluation orchestration yet

## 10. Current Truth

If someone asks "what does the project do right now", this document is the intended answer.

If deeper design detail is needed, follow the document map in [README.md](./README.md).
