# dj-lineage-backend

A sustainable Python lineage backend scaffold for DJ Panel built with:

- FastAPI
- SQLAlchemy Core
- Alembic
- PostgreSQL

This backend is intentionally scoped to a `JobVersion Lite` model:

- accepts OpenLineage events
- stores raw events in `lineage_events`
- projects batch-oriented table-level lineage into relational tables
- computes a stable `job_version` on `COMPLETE`
- snapshots output `dataset_versions` on `COMPLETE`
- serves a current-version lineage graph
- exposes Marquez-friendly metadata endpoints for jobs, datasets, runs, facets, and namespaces

Not in scope for this first version:

- column-level lineage
- streaming-specific version semantics
- complex backfill / replay reconciliation
- fine-grained job version diffing

## Directory layout

```text
dj-lineage-backend/
├── alembic/
├── app/
│   ├── api/routes/
│   ├── db/
│   ├── models/
│   ├── repositories/
│   └── services/
├── alembic.ini
├── pyproject.toml
└── README.md
```

## Quick start

```bash
cd standalone/dj-lineage-backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

Run the baseline tests with:

```bash
source .venv/bin/activate
pytest tests/test_smoke.py tests/test_ingestion_flow.py tests/test_api_compat.py -q
```

The integration-style ingestion tests use OpenLineage `RunEvent` fixtures under
`tests/fixtures/` and verify:

- `START -> COMPLETE` run state evolution
- `job_versions` creation on `COMPLETE`
- `run/job/dataset facets` projection

## Environment

Create a `.env` file like this:

```bash
DATABASE_URL=postgresql+psycopg://dludora@localhost:5432/dj_panel
APP_ENV=dev
```

## API surface

- `GET /health`
- `POST /api/v1/lineage`
- `GET /api/v1/lineage?nodeId=job:namespace:name&depth=2`
- `GET /api/v1/events/lineage?limit=50`
- `GET /api/v1/namespaces`
- `GET /api/v1/jobs?limit=25&offset=0&lastRunStates=COMPLETED`
- `GET /api/v1/namespaces/{namespace}/jobs`
- `GET /api/v1/namespaces/{namespace}/jobs/{job}`
- `GET /api/v1/namespaces/{namespace}/jobs/{job}/runs`
- `GET /api/v1/namespaces/{namespace}/datasets`
- `GET /api/v1/namespaces/{namespace}/datasets/{dataset}`
- `GET /api/v1/namespaces/{namespace}/datasets/{dataset}/versions`
- `GET /api/v1/jobs/runs/{runId}/facets?type=run|job`

## JobVersion Lite semantics

- all runs keep their real input and output dataset mappings
- only `COMPLETE` events update `job_versions`
- the current lineage graph reads from the current `job_version`
- failed runs are stored but do not advance the current version

## Recommended next steps

1. add integration tests against PostgreSQL
2. add DJ-specific facets and asset kinds
3. add dataset versioning if model artifacts need stronger identities
4. add remaining Marquez web compatibility endpoints such as search, tags, deletes, and column-level lineage
