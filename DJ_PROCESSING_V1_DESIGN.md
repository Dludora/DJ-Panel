# Data-Juicer Processing V1 Design

## 1. Scope

This document defines the first product version of the internal team tool with one narrow focus:

- Data-Juicer recipe management
- processing request submission
- DJ worker claiming and execution
- OpenLineage ingestion and projection
- output dataset tracking and review

This version does not yet try to unify:

- model training orchestration
- evaluation orchestration
- generic multi-runtime workers
- complex multi-step DAG scheduling inside the control plane

The first version should feel like a shared team tool for dataset processing rather than a general workflow engine.

## 2. Product Shape

In V1, the tool should look like four connected work areas:

- `Recipes`
  Manage Data-Juicer recipes and versions.
- `Datasets`
  Browse input and output dataset versions.
- `Submissions`
  Submit and monitor processing requests.
- `Lineage`
  Inspect what actually happened through OpenLineage.

There should also be a lightweight `Workers` view for debugging and operations.

## 3. Core User Journey

The main V1 journey is:

1. A team member imports or creates a recipe.
2. They publish a new `RecipeVersion`.
3. They choose one or more input dataset versions.
4. They submit one processing request.
5. The backend creates one `RunSubmission`.
6. The backend creates one claimable `Task`.
7. One DJ worker claims the task and executes Data-Juicer.
8. Data-Juicer emits OpenLineage events automatically.
9. The backend projects observed jobs, runs, inputs, outputs, and dataset versions.
10. The team reviews outputs and lineage in the UI.

V1 should optimize for this one workflow.

## 4. V1 Object Model

For V1, we only need a small set of user-facing concepts.

### 4.1 User-Facing Concepts

- `Recipe`
  A human-facing processing recipe identity.
- `RecipeVersion`
  An immutable Data-Juicer recipe snapshot.
- `Dataset`
  A logical dataset identity.
- `DatasetVersion`
  A versioned dataset instance.
- `RunSubmission`
  A user request to run one recipe version with concrete inputs.
- `Observed Run`
  The OpenLineage runtime fact emitted by Data-Juicer.

### 4.2 Infrastructure Concepts

- `Worker`
  A DJ execution agent.
- `Task`
  A dispatch unit created from a submission.
- `TaskAttempt`
  A concrete execution attempt.
- `TaskLog`
  Execution logs.
- `TaskArtifact`
  Registered output artifacts or references.

### 4.3 Important Boundary

In V1:

- `RunSubmission` is what the user asked for
- `Task` is how the system dispatches work
- `Observed Run` is what DJ actually reported through OpenLineage

This distinction is central to the design.

## 5. V1 Commands

### 5.1 Backend Command

The backend should eventually be started with:

```bash
dj-panel master
```

Development fallback:

```bash
uvicorn app.main:app --reload
```

### 5.2 DJ Worker Command

The V1 worker should be explicitly DJ-specific:

```bash
dj-panel worker dj \
  --workspace llm-team \
  --worker-id dj-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-panel-worker \
  --dj-bin dj-process \
  --poll-interval 5
```

This is better than a generic `dj-panel-worker` because V1 is intentionally scoped to Data-Juicer processing.

Argument meaning:

- `workdir`
  Local scratch space for one worker process. This is only for temporary execution files such as materialized recipe configs, transient logs, and task-local cache.
- `dj-bin`
  The Data-Juicer executable available in the current environment. In most cases this should be `dj-process`.

V1 should not rely on a worker-level `datasets-root` argument. Dataset locations should come from `Datasets` and `DatasetVersions` managed by the backend.

### 5.3 Recipe Import and Publish Commands

The UI should be the primary recipe management path, but a CLI is still useful for developers.

Recommended commands:

```bash
dj-panel recipe import ./recipes/cleaning.yaml \
  --workspace llm-team \
  --name sft-cleaning
```

```bash
dj-panel recipe publish ./recipes/cleaning_v2.yaml \
  --workspace llm-team \
  --recipe sft-cleaning
```

Optional inspection command:

```bash
dj-panel recipe validate ./recipes/cleaning_v2.yaml
```

## 6. What the DJ Worker Should Actually Do

The V1 worker should be a long-running DJ-aware executor, not just a generic shell runner.

When started, it should:

1. register itself as a DJ worker
2. send heartbeat on a fixed interval
3. poll for claimable DJ tasks
4. claim only tasks it knows how to execute
5. materialize the claimed recipe version locally
6. construct the Data-Juicer runtime config and command
7. run Data-Juicer in a controlled work directory
8. stream stdout and stderr back to the backend
9. register produced artifacts and output references
10. mark success or failure

The worker should not be responsible for producing custom lineage logic. It should rely on the installed Data-Juicer OpenLineage plugin.

## 7. Claiming Model

In V1, a worker should not try to claim arbitrary tasks.

It should only claim tasks that match its execution contract.

For the DJ worker, the backend task should indicate:

- `task_kind = dj_recipe`

That means:

- the task payload is a Data-Juicer recipe execution payload
- the worker is expected to know how to materialize and run it

The user never edits the queue directly. The queue is derived automatically:

- user creates `RunSubmission`
- backend creates `Task`
- DJ worker claims `Task`

The queue is not edited directly by users. Team members create submissions through the UI or CLI, and the backend derives claimable tasks from those submissions.

## 8. V1 Task Payload

The claimed task payload should be semantic and DJ-specific.

It should not just be a raw shell command.

Recommended payload shape:

```json
{
  "claimed": true,
  "task": {
    "taskId": "uuid",
    "attemptId": "uuid",
    "leaseToken": "uuid-or-random-token",
    "taskKind": "dj_recipe",
    "timeoutSeconds": 7200,
    "submission": {
      "id": "uuid",
      "workspaceSlug": "llm-team",
      "requestedBy": "alice",
      "parameters": {
        "sample_size": 100000
      }
    },
    "recipeVersion": {
      "id": "uuid",
      "recipeId": "uuid",
      "recipeName": "sft-cleaning",
      "version": 7,
      "rawYaml": "...",
      "recipeHash": "sha256:...",
      "projectName": "clean_sft",
      "executorType": "standalone",
      "djVersion": "x.y.z",
      "pipelineJobNamespace": "llm-team.processing",
      "pipelineJobName": "sft-cleaning"
    },
    "inputs": [
      {
        "datasetVersionId": "uuid",
        "namespace": "llm-team.datasets",
        "name": "raw_sft",
        "version": "2026-04-25",
        "storageUri": "s3://bucket/raw_sft/2026-04-25"
      }
    ],
    "outputs": [
      {
        "namespace": "llm-team.datasets",
        "name": "clean_sft",
        "declaredVersion": "auto",
        "storageUri": "s3://bucket/clean_sft/next"
      }
    ],
    "runtime": {
      "workdir": "/tmp/dj-panel-worker/tasks/uuid",
      "envVars": {
        "OPENLINEAGE_URL": "http://127.0.0.1:8000/api/v1/lineage"
      },
      "overrides": {
        "sample_size": 100000
      }
    }
  }
}
```

Key point:

- the backend sends structured DJ intent
- dataset locations come from registered dataset versions
- the worker builds the DJ command from that payload
- the worker does not infer dataset paths from one global root path

## 9. How the Worker Executes Data-Juicer

The worker execution flow should be:

1. write `recipeVersion.rawYaml` to a local file
2. resolve input dataset locations from `inputs`
3. resolve output targets from `outputs`
4. merge `runtime.overrides` into the recipe execution parameters
5. prepare environment variables for OpenLineage emission
6. materialize a runnable DJ config file in `runtime.workdir`
7. run the DJ command in `runtime.workdir`

Example execution shape:

```bash
dj-process \
  --config /tmp/dj-panel-worker/tasks/<task-id>/recipe.yaml
```

The resulting config should already contain the resolved input and output locations derived from `DatasetVersion` records and submission overrides.

For V1, the important part is:

- the DJ worker runs the real Data-Juicer CLI shape
- the worker materializes a config file first
- `DatasetVersion.storage_uri` is the source of dataset location truth

The worker should not need to do this:

```bash
dj-process --config /tmp/dj-panel-worker/tasks/<task-id>/recipe.yaml \
  --dataset_path s3://bucket/raw_sft/2026-04-25 \
  --export_path s3://bucket/clean_sft/next
```

unless the DJ recipe contract explicitly requires those paths as runtime CLI overrides.

## 10. Recipe Management in V1

Recipe management should be append-only by version.

### 10.1 Create Recipe

The user creates a logical recipe entry:

- name
- description
- optional tags

### 10.2 Publish Recipe Version

Each update creates a new immutable `RecipeVersion`:

- raw YAML
- recipe hash
- normalized DAG JSON
- operator names
- DJ version
- optional git metadata

No in-place mutation should be allowed for published versions.

### 10.3 Update Recipe

Updating a recipe means:

- start from an existing version or local YAML
- edit it
- publish a new version

The tool should present this as:

- `Recipe` = long-lived identity
- `RecipeVersion` = immutable snapshot

## 11. How Users Manage Recipes

V1 should support two recipe update paths.

### 11.1 UI Path

Primary flow:

1. open recipe page
2. create recipe or choose an existing one
3. upload or paste YAML
4. review parsed operator structure
5. publish a new version

### 11.2 CLI Path

Developer flow:

1. edit YAML locally
2. import or publish via CLI
3. inspect the new recipe version in the UI

The UI should remain the shared source of visibility, even if local authoring continues outside the tool.

## 12. V1 Backend Endpoints

### 12.1 Existing Endpoints to Keep

- workspace create/list
- recipe create/list/get/version list
- worker register/list/heartbeat
- task claim/get/start/complete/fail/cancel
- task attempt logs and artifacts
- lineage ingestion and metadata query

### 12.2 V1 Additions Recommended

- `POST /api/v1/workspaces/{workspace_slug}/run-submissions`
- `GET /api/v1/workspaces/{workspace_slug}/run-submissions`
- `GET /api/v1/run-submissions/{submission_id}`

These endpoints should replace the product-facing role currently carried by `recipe-runs`.

### 12.3 Transitional Compatibility

If implementation speed matters, the current `recipe-runs` endpoint can temporarily serve as the V1 submission API, but the UI and product language should already treat it as a processing submission rather than a generic run table.

## 13. V1 Frontend Pages

### 13.1 Recipes

Functions:

- list recipes
- show recipe versions
- show YAML
- show parsed operators
- publish new version

### 13.2 Datasets

Functions:

- list dataset versions
- show schema and basic stats
- show producer lineage
- show consumer lineage
- show registered storage location and dataset identity

V1 should treat `Datasets` as the single data entrypoint.

That means:

- dataset identity comes from projected lineage and managed metadata together
- dataset location for worker execution comes from `DatasetVersion`
- users should not have to reason about a separate worker-local dataset root

### 13.3 Processing Submissions

Functions:

- submit a recipe version against input datasets
- show queued, claimed, running, succeeded, failed states
- show which worker claimed the submission task
- link to observed lineage runs

### 13.4 Runs

Functions:

- show observed pipeline runs
- show observed operator runs
- show lineage facets and timing

### 13.5 Workers

Functions:

- show worker availability
- show claim activity
- show failed attempts and logs

## 14. Team Usage in V1

In V1, the tool should support this daily usage pattern:

### Data Engineer

- publishes recipe versions
- submits processing requests
- compares output datasets

### Research Engineer

- reviews processed dataset versions
- decides which output dataset should feed the next stage

### Team Lead or Reviewer

- compares recipe versions
- checks lineage and data provenance
- approves which output dataset version becomes the new baseline

### Infra Maintainer

- watches workers
- checks failed attempts
- inspects logs and execution issues

## 15. What V1 Should Not Try to Solve Yet

To keep V1 sharp, do not expand scope into:

- training worker orchestration
- evaluation orchestration
- arbitrary generic command execution
- complex submission splitting into many tasks
- internal DAG scheduling beyond one DJ processing submission producing one primary task

V1 should be opinionated:

- one submission
- one primary DJ task
- one DJ worker claims it
- many observed lineage runs may still appear because DJ emits pipeline and operator events

## 16. Recommended V1 Summary

The clearest V1 design is:

- recipes are versioned and managed as first-class authoring objects
- users submit processing requests from recipe versions plus input datasets
- the backend creates one DJ-specific task
- a DJ-specific worker claims that task and runs Data-Juicer
- OpenLineage provides the runtime truth
- the UI helps the team compare recipes, submissions, observed runs, and output datasets

That is a narrow but strong first version for the internal team tool.
