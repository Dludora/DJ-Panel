# DJ Panel Backend

Merged backend for DJ Panel, combining:

- workspace-aware control-plane orchestration
- asset catalog management
- OpenLineage event ingestion and projection
- lineage browse and graph queries

This service currently covers:

- workspaces
- versioned recipes
- run submissions
- tasks and task attempts
- worker registration and heartbeat
- atomic task claiming
- execution log file artifacts and other artifact references
- lineage/MLflow linkage fields on task attempts
- lineage event ingestion and projection
- asset catalog and lineage browse APIs for jobs, runs, assets, versions, and facets

## Docs

The main documentation entrypoints are:

- [docs/README.md](./docs/README.md)
  Documentation map and document boundaries.
- [docs/CURRENT_PROJECT.md](./docs/CURRENT_PROJECT.md)
  Current project overview and present-state behavior.

The deeper design documents live under `docs/`:

- [docs/api/openapi.yaml](./docs/api/openapi.yaml)
- [docs/run/RUN_SUBMISSION_SPEC.md](./docs/run/RUN_SUBMISSION_SPEC.md)
- [docs/worker/data-juicer/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./docs/worker/data-juicer/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)
- [docs/worker/train_eval/SFT_MLFLOW_LINEAGE_DESIGN.md](./docs/worker/train_eval/SFT_MLFLOW_LINEAGE_DESIGN.md)
- [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md)
  Runtime environment defaults and operator configuration entrypoints.

## Quick start

From the backend operator's point of view, the fastest local setup is:

1. install dependencies
2. start the backend with a local SQLite database
3. optionally start the web dev server
4. configure your local CLI defaults
5. create a workspace and start using `recipe` / `run` / `worker`

### 1. Install

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
cp .env.example .env
```

### 2. Start the backend with SQLite

SQLite is the recommended default for first local startup.

First start:

```bash
dj-panel master \
  --database-url sqlite:///./dj_panel.db \
  --migrate
```

Backend development:

```bash
dj-panel master \
  --database-url sqlite:///./dj_panel.db \
  --migrate \
  --reload
```

Notes:

- `--migrate` upgrades the database schema before the server starts; keep it for first local startup and after schema changes.
- `--reload` is only for backend development; it automatically restarts the server when Python files change.

The backend will be available at:

```text
http://127.0.0.1:8000
```

### 3. Start the web dev server

Once the backend is running, you can start the in-repo frontend dev server:

```bash
dj-panel web --backend-url http://127.0.0.1:8000 --install-deps
```

The web app will be available at:

```text
http://127.0.0.1:1337
```

Notes:

- `dj-panel web` uses the in-repo `web/` directory by default.
- `--install-deps` runs `npm install` before startup; you usually only need it the first time or after frontend dependency changes.

### 4. Configure local CLI defaults

Set the base URL and your common local defaults before creating resources:

```bash
dj-panel config set \
  --base-url http://127.0.0.1:8000 \
  --workspace team-a \
  --user alice

dj-panel config show
```

### 5. Create a workspace

```bash
dj-panel workspace create team-a \
  --name "Team A" \
  --owner alice \
  --use
```

After that, the normal day-to-day flow is:

- `dj-panel recipe import ...`
- `dj-panel recipe publish ...`
- `dj-panel run submit ...`
- `dj-panel worker dj ...`

### Optional: PostgreSQL instead of SQLite

If you prefer PostgreSQL locally, create the database first:

```bash
createdb dj_panel
```

Then start the backend with:

```bash
dj-panel master \
  --database-url postgresql+psycopg:///dj_panel \
  --migrate
```

Or use an explicit connection string:

```bash
dj-panel master \
  --database-url postgresql+psycopg://user:pass@localhost:5432/dj_panel \
  --host 0.0.0.0 \
  --port 8000 \
  --migrate
```

For all supported runtime environment variables and precedence rules, see
[docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md).

## Shared backend / multi-user CLI

If multiple users share one central backend, each user runs the CLI on their own machine
and points it to the same `base-url`.

Example for Alice:

```bash
dj-panel config set \
  --base-url http://<master-host>:8000 \
  --workspace team-a \
  --user alice
```

Example for Bob:

```bash
dj-panel config set \
  --base-url http://<master-host>:8000 \
  --workspace team-a \
  --user bob
```

Notes:

- `--base-url` tells the CLI which shared backend to talk to.
- `--user` declares the default user identity for CLI operations from that machine.
- `workspace members add` manages team membership in the backend, while `config set --user ...` controls who the local CLI acts as by default.

## Common CLI flow

Create a workspace:

```bash
dj-panel workspace create team-a \
  --name "Team A" \
  --owner alice \
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

dj-panel recipe download \
  --recipe sft-cleaning \
  --output ./sft-cleaning.yaml
```

Submit a processing run submission from a spec.
See [docs/run/RUN_SUBMISSION_SPEC.md](./docs/run/RUN_SUBMISSION_SPEC.md) for the
current processing spec shape and examples:

```bash
dj-panel run submit \
  --workspace team-a \
  --kind processing \
  --spec ./process_spec.yaml \
  --requested-by alice
```

Most commands now use a human-readable table or key/value format by default. Add `--json`
when you want the raw API payload.

## Minimal flow

1. Create a workspace
2. Create a recipe, which also creates version 1
3. Create a run submission in that workspace
4. Register a worker
5. Worker claims the pending task
6. Worker starts, writes local log files, registers artifacts, and completes or fails

## Worker client

The V1 worker is Data-Juicer-specific. It registers itself as a DJ worker, claims only
`dj_recipe` tasks, materializes the claimed recipe into `<workdir>/tasks/<task_id>/recipe.yaml`,
passes `--job_id <task_id>`, aligns DJ's final `work_dir` to that same task directory,
and captures execution output in `<workdir>/tasks/<task_id>/run.log`.

```bash
dj-panel worker dj \
  --worker-id local-dev-1 \
  --workdir /tmp/dj-panel-worker \
  --dj-bin dj-process \
  --poll-interval 5
```

For a detailed breakdown of APIs, tables, flows, and current gaps, see
[docs/README.md](./docs/README.md).
