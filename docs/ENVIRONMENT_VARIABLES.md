# Environment Variables

This document is the source-of-truth reference for runtime defaults that can be
configured through environment variables in `dj-panel-backend`.

The goal is:

- no important runtime default is hidden inside random files
- backend, CLI, and worker defaults are configurable from one place
- operators can see which environment variables affect behavior

This document covers runtime and operator defaults only. Business-level protocol
defaults such as `submissionKind=processing` or `role=MEMBER` still
live with the API/domain models and are not treated as environment-configurable
deployment settings.

All defaults are defined in [app/config.py](/Users/dludora/Code/DJ-Panel/dj-panel-backend/app/config.py).

## Resolution Rules

`dj-panel-backend` uses these layers:

1. explicit CLI arguments
2. local CLI config file from `DJ_PANEL_CLI_CONFIG_PATH` for `workspace`, `user`, and `base-url`
3. environment variables
4. code-level defaults in `app/config.py`

For backend settings such as database URL and lease duration, the main sources are:

1. explicit CLI arguments
2. environment variables
3. code-level defaults in `app/config.py`

## Backend

### `DATABASE_URL`

Alias:
- `DJ_PANEL_DATABASE_URL`

Default:
- `sqlite:///./dj_panel.db`

Used by:
- backend database engine
- Alembic migrations
- `dj-panel master --database-url ...` overrides this value for the current process

Example:

```bash
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/dj_panel
```

### `APP_ENV`

Alias:
- `DJ_PANEL_APP_ENV`

Default:
- `dev`

Used by:
- backend runtime environment labeling

### `CLAIM_LEASE_SECONDS`

Alias:
- `DJ_PANEL_CLAIM_LEASE_SECONDS`

Default:
- `900`

Used by:
- task claim lease expiration in [tasks_repo.py](/Users/dludora/Code/DJ-Panel/dj-panel-backend/dj_panel/app/repositories/tasks_repo.py)

## API / CLI Defaults

### `BASE_URL`

Alias:
- `DJ_PANEL_BASE_URL`

Default:
- `http://127.0.0.1:8000`

Used by:
- CLI default backend address when neither `--base-url` nor local CLI config provides one

Example:

```bash
export DJ_PANEL_BASE_URL=http://10.0.0.8:8000
```

### `HTTP_TIMEOUT_SECONDS`

Alias:
- `DJ_PANEL_HTTP_TIMEOUT_SECONDS`

Default:
- `30`

Used by:
- CLI HTTP client timeout
- worker execution HTTP client timeout

## Backend Server

### `HOST`

Alias:
- `DJ_PANEL_HOST`

Default:
- `127.0.0.1`

Used by:
- `dj-panel master --host` default value

### `PORT`

Alias:
- `DJ_PANEL_PORT`

Default:
- `8000`

Used by:
- `dj-panel master --port` default value

## Web Dev Server

### `DJ_PANEL_WEB_HOST`

Default:
- `127.0.0.1`

Used by:
- `dj-panel web --host` default value

### `DJ_PANEL_WEB_PORT`

Default:
- `1337`

Used by:
- `dj-panel web --port` default value

### `DJ_PANEL_WEB_DIR`

Default:
- unset as a literal env var
- if unset in the environment, the runtime default path is the sibling `dj-panel-web` directory next to `dj-panel-backend`

Used by:
- `dj-panel web --web-dir` default value
- if unset, CLI falls back to the sibling `dj-panel-web` directory

### `DJ_PANEL_NPM_BIN`

Default:
- `npm`

Used by:
- `dj-panel web --npm-bin` default value

### `DJ_PANEL_WEB_OPEN`

Default:
- `false`

Used by:
- `dj-panel web --open/--no-open` default value

## Worker / Execution

### `DJ_PANEL_WORKDIR`

Default:
- `/tmp/dj-panel-worker`

Used by:
- `dj-panel worker ... --workdir` default value

### `DJ_PANEL_WORKER_POLL_INTERVAL_SECONDS`

Alias:
- `DJ_PANEL_POLL_INTERVAL_SECONDS`

Default:
- `0`

Used by:
- `dj-panel worker ... --poll-interval` default value

### `DJ_PANEL_DJ_BIN`

Default:
- `dj-process`

Used by:
- `dj-panel worker dj --dj-bin` default value
- default recipe command generation for DJ recipe publish/import helpers

### `DJ_PANEL_DJ_CONFIG_ARG`

Default:
- `--config`

Used by:
- default Data-Juicer command construction

Derived default command:

```text
<DJ_PANEL_DJ_BIN> <DJ_PANEL_DJ_CONFIG_ARG> recipe.yaml
```

With default values this becomes:

```text
dj-process --config recipe.yaml
```

### `DJ_PANEL_RECIPE_TIMEOUT_SECONDS`

Default:
- `7200`

Used by:
- `dj-panel recipe import --timeout-seconds` default value
- `dj-panel recipe publish --timeout-seconds` default value

### `DJ_PANEL_CLI_CONFIG_PATH`

Default:
- `~/.config/dj-panel/config.json`

Used by:
- local CLI config storage for `workspace`, `user`, and `base-url`
- `dj-panel config set`
- `dj-panel config show`

## `.env` Support

`app/config.py` loads `.env` automatically through `pydantic-settings`.

Example:

```env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/dj_panel
DJ_PANEL_BASE_URL=http://127.0.0.1:8000
DJ_PANEL_HOST=0.0.0.0
DJ_PANEL_PORT=8000
DJ_PANEL_WEB_OPEN=false
DJ_PANEL_WORKDIR=/mnt/dj-panel-worker
DJ_PANEL_WORKER_POLL_INTERVAL_SECONDS=5
DJ_PANEL_DJ_BIN=dj-process
DJ_PANEL_HTTP_TIMEOUT_SECONDS=60
DJ_PANEL_RECIPE_TIMEOUT_SECONDS=7200
DJ_PANEL_CLI_CONFIG_PATH=~/.config/dj-panel/config.json
```

## Notes

- Local CLI config and environment variables are different:
  - local CLI config stores user defaults like `workspace`, `user`, `base-url`
  - environment variables define process-level runtime defaults
- If both are present for CLI base URL:
  - explicit `--base-url` wins
  - local CLI config wins over environment
  - environment wins over code default
