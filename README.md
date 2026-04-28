# DJ Panel Backend

Merged backend for DJ Panel, combining:

- workspace-aware control-plane orchestration
- OpenLineage ingestion
- lineage graph queries
- Marquez-style metadata endpoints

This service currently covers:
- workspaces
- versioned recipes
- run submissions
- tasks and task attempts
- worker registration and heartbeat
- atomic task claiming
- task logs and artifact references
- lineage/MLflow linkage fields on task attempts
- lineage event ingestion
- metadata projection for jobs, runs, datasets, versions, and facets

## Docs

The main documentation entrypoints are:

- [docs/README.md](./docs/README.md)
  Documentation map and document boundaries.
- [docs/CURRENT_PROJECT.md](./docs/CURRENT_PROJECT.md)
  Current project overview and present-state behavior.

The deeper design documents live under `docs/`:

- [docs/TARGET_ARCHITECTURE.md](./docs/TARGET_ARCHITECTURE.md)
- [docs/DJ_PROCESSING_V1_DESIGN.md](./docs/DJ_PROCESSING_V1_DESIGN.md)
- [docs/DATABASE_SCHEMA_DRAFT.md](./docs/DATABASE_SCHEMA_DRAFT.md)
- [docs/V1_API_OPENAPI_STYLE.md](./docs/V1_API_OPENAPI_STYLE.md)
- [docs/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./docs/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)

## Quick start

```bash
cd dj-panel-backend
uv sync --extra dev
cp .env.example .env
createdb dj_panel  # only if the database does not already exist
.venv/bin/dj-panel master --migrate --reload
```

Default local database URL:

```bash
postgresql+psycopg:///dj_panel
```

This uses the local PostgreSQL server and the current OS user by default.

You can also pass an explicit database URL:

```bash
dj-panel master \
  --database-url postgresql+psycopg://user:pass@localhost:5432/dj_panel \
  --host 0.0.0.0 \
  --port 8000 \
  --migrate
```

## Recipe CLI

Create a workspace:

```bash
dj-panel workspace create team-a \
  --name "Team A" \
  --owner alice \
  --base-url http://127.0.0.1:8000 \
  --use
```

Store or inspect local CLI defaults:

```bash
dj-panel config set \
  --workspace team-a \
  --user alice \
  --base-url http://127.0.0.1:8000

dj-panel config show
```

Manage workspace members:

```bash
dj-panel workspace members add \
  --user bob \
  --role MAINTAINER

dj-panel workspace members list \
  --workspace team-a
```

Import a new Data-Juicer recipe:

```bash
dj-panel recipe import ./recipes/cleaning.yaml \
  --name sft-cleaning \
  --owner alice
```

Publish a new version of an existing recipe:

```bash
dj-panel recipe publish ./recipes/cleaning_v2.yaml \
  --recipe sft-cleaning \
  --owner alice
```

List and inspect recipes:

```bash
dj-panel recipe list

dj-panel recipe show \
  --recipe sft-cleaning
```

Submit a run submission from the current recipe version:

```bash
dj-panel run submit \
  --recipe sft-cleaning \
  --requested-by alice \
  --parameters '{"np": 4}'
```

Most commands now use a human-readable table or key/value format by default. Add `--json`
when you want the raw API payload.

## Minimal flow

1. Create a workspace
2. Create a recipe, which also creates version 1
3. Create a run submission in that workspace
4. Register a worker
5. Worker claims the pending task
6. Worker starts, logs, uploads artifacts, and completes or fails

## Worker client

The V1 worker is Data-Juicer-specific. It registers itself as a DJ worker, claims only
`dj_recipe` tasks, materializes the claimed recipe into a local `recipe.yaml`, and runs
Data-Juicer with `dj-process --config`.

```bash
dj-panel worker dj \
  --worker-id local-dev-1 \
  --workdir /tmp/dj-panel-worker \
  --dj-bin dj-process \
  --poll-interval 5
```

For a detailed breakdown of APIs, tables, flows, and current gaps, see
[docs/README.md](./docs/README.md).
