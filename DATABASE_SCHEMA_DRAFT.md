# Database Schema Draft

## 1. Design Principles

This draft follows the current architecture discussion for the internal team tool:

- Data-Juicer and MLflow emit OpenLineage events automatically
- OpenLineage is the runtime fact backbone
- the tool should not duplicate `jobs`, `runs`, `run_inputs`, or `run_outputs` with a second parallel fact model
- the tool should only add authoring, submission, dispatch, attempt, and collaboration objects
- future model management should reuse the same lineage-derived asset pipeline as datasets
- dataset and model distinction should come from projected facet semantics rather than from two unrelated runtime fact systems

## 2. High-Level Domains

The schema is split into five domains:

- organization
- recipe authoring
- lineage raw events
- lineage projections
- tool dispatch

## 3. Organization Domain

### `workspaces`

Logical collaboration boundary.

Columns:

- `id` UUID PK
- `slug` varchar unique not null
- `name` varchar not null
- `description` text not null default `''`
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

### `workspace_members`

Optional team membership and role model.

Columns:

- `id` UUID PK
- `workspace_id` UUID FK -> `workspaces.id`
- `user_name` varchar not null
- `role` varchar not null default `MEMBER`
- `created_at` timestamptz not null default `now()`

Constraints:

- unique (`workspace_id`, `user_name`)

## 4. Recipe Authoring Domain

### `recipes`

Human-facing logical recipe identity.

Columns:

- `id` UUID PK
- `workspace_id` UUID FK -> `workspaces.id`
- `name` varchar not null
- `slug` varchar not null
- `description` text not null default `''`
- `created_by` varchar null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`workspace_id`, `slug`)

### `recipe_versions`

Immutable Data-Juicer recipe snapshot.

Columns:

- `id` UUID PK
- `recipe_id` UUID FK -> `recipes.id`
- `version` integer not null
- `raw_yaml` text not null
- `recipe_hash` varchar not null
- `normalized_dag_json` jsonb not null default `'{}'::jsonb`
- `operator_names` jsonb not null default `'[]'::jsonb`
- `project_name` varchar null
- `executor_type` varchar null
- `config_path` text null
- `dj_version` varchar null
- `source_type` varchar null
- `git_repo_url` text null
- `git_commit` varchar null
- `git_branch` varchar null
- `git_tag` varchar null
- `pipeline_job_namespace` varchar null
- `pipeline_job_name` varchar null
- `pipeline_job_version_id` UUID null
- `created_by` varchar null
- `created_at` timestamptz not null default `now()`

Constraints:

- unique (`recipe_id`, `version`)

Notes:

- `pipeline_job_namespace` and `pipeline_job_name` point to the projected primary OpenLineage pipeline job identity.
- `pipeline_job_version_id` is optional because lineage projection may happen after recipe storage.

### `recipe_version_operators`

Static operator metadata extracted from a recipe version for workstation rendering and diffing.

Columns:

- `id` UUID PK
- `recipe_version_id` UUID FK -> `recipe_versions.id`
- `op_index` integer not null
- `op_name` varchar not null
- `op_type` varchar null
- `op_config_hash` varchar null
- `op_args_json` jsonb not null default `'{}'::jsonb`
- `code_repo_url` text null
- `code_relative_path` text null
- `file_path` text null
- `git_commit` varchar null
- `git_branch` varchar null
- `git_tag` varchar null
- `created_at` timestamptz not null default `now()`

Constraints:

- unique (`recipe_version_id`, `op_index`)

## 5. Lineage Raw Event Domain

### `lineage_events`

Append-only raw OpenLineage payload storage.

Columns:

- `id` UUID PK
- `event_type` varchar not null
- `event_time` timestamptz null
- `producer` text null
- `job_namespace` varchar null
- `job_name` varchar null
- `run_id` varchar null
- `payload` jsonb not null
- `created_at` timestamptz not null default `now()`

Indexes:

- `ix_lineage_events_run_id` on `run_id`
- `ix_lineage_events_created_at` on `created_at`

## 6. Lineage Projection Domain

These tables are projected from OpenLineage events and are the canonical definition and runtime fact layer.

### 6.0 Current Implementation vs V1 Target

Current backend implementation already provides:

- `datasets`
- `dataset_versions`
- `dataset_facets`
- `run_inputs`
- `run_outputs`

For V1, the recommended direction is to extend this existing shape rather than replace it with a separate asset table.

That means:

- keep `datasets` as the primary asset identity table
- keep `dataset_versions` as the primary version table
- allow both dataset-like and model-like assets to live in these same tables
- distinguish them through facet-derived classification

### `namespaces`

- `name` varchar PK
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`
- `owner_name` varchar not null default `''`
- `description` text not null default `''`
- `is_hidden` boolean not null default `false`

### `jobs`

Projected OpenLineage jobs.

Columns:

- `id` UUID PK
- `namespace` varchar not null
- `name` varchar not null
- `job_kind` varchar null
- `location` text null
- `current_job_version_id` UUID null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`namespace`, `name`)

Recommended `job_kind` values:

- `processing_pipeline`
- `processing_operator`
- `training`
- `evaluation`

### `job_versions`

Projected versions of one job identity.

Columns:

- `id` UUID PK
- `job_id` UUID FK -> `jobs.id`
- `version_hash` varchar not null
- `is_current` boolean not null default `false`
- `created_at` timestamptz not null default `now()`

Constraints:

- unique (`job_id`, `version_hash`)

### `runs`

Observed OpenLineage runs.

Columns:

- `id` UUID PK
- `run_id` varchar not null
- `job_id` UUID FK -> `jobs.id`
- `job_version_id` UUID FK -> `job_versions.id` null
- `parent_run_id` UUID FK -> `runs.id` null
- `event_time` timestamptz null
- `state` varchar null
- `started_at` timestamptz null
- `ended_at` timestamptz null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`run_id`)

Notes:

- `parent_run_id` is especially useful for Data-Juicer operator-level runs linked to a pipeline run.

### `datasets`

Projected OpenLineage dataset identities.

Columns:

- `id` UUID PK
- `namespace` varchar not null
- `name` varchar not null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`namespace`, `name`)

Current implementation:

- current schema only stores `id`, `namespace`, `name`, `created_at`, `updated_at`

Recommended V1 additions:

- `asset_kind` varchar not null default `DATASET`

Recommended `asset_kind` values:

- `DATASET`
- `MODEL`
- `CHECKPOINT`
- `EVAL_REPORT`
- `OTHER`

Notes:

- `asset_kind` should be computed from projected OpenLineage facets rather than manually authored.
- A future `models` product view should be backed by the same `datasets` table filtered by `asset_kind = MODEL`.
- `CHECKPOINT`
- `EVAL_REPORT`
- `OTHER`

### `dataset_versions`

Versioned projected assets.

Columns:

- `id` UUID PK
- `dataset_id` UUID FK -> `datasets.id`
- `version` varchar not null
- `created_by_run_id` UUID FK -> `runs.id` null
- `fields` jsonb not null default `'[]'::jsonb`
- `facets` jsonb not null default `'{}'::jsonb`
- `lifecycle_state` varchar null
- `created_at` timestamptz not null default `now()`

Constraints:

- unique (`dataset_id`, `version`)

Current implementation:

- current schema already stores `fields`, `facets`, `lifecycle_state`, and `created_by_run_id`
- current schema does not yet expose `storage_uri` as a first-class column

Recommended V1 additions:

- `storage_uri` text null

Notes:

- `storage_uri` should be treated as the primary execution-facing location for V1 Data-Juicer tasks.
- DJ workers should resolve dataset input and output locations from dataset records rather than from one worker-global datasets root.
- `dataset_versions` should be able to represent model versions as well, as long as classification and rendering use `datasets.asset_kind` plus version facets.

### `run_inputs`

- `run_id` UUID FK -> `runs.id`
- `dataset_id` UUID FK -> `datasets.id`
- PK (`run_id`, `dataset_id`)

### `run_outputs`

- `run_id` UUID FK -> `runs.id`
- `dataset_id` UUID FK -> `datasets.id`
- PK (`run_id`, `dataset_id`)

### `run_facets`

- `id` UUID PK
- `run_id` UUID FK -> `runs.id`
- `facet_name` varchar not null
- `payload` jsonb not null
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`run_id`, `facet_name`)

### `job_facets`

- `id` UUID PK
- `job_id` UUID FK -> `jobs.id`
- `facet_name` varchar not null
- `payload` jsonb not null
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`job_id`, `facet_name`)

### `dataset_facets`

- `id` UUID PK
- `dataset_id` UUID FK -> `datasets.id`
- `facet_name` varchar not null
- `payload` jsonb not null
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`dataset_id`, `facet_name`)

Notes:

- this table is the right place to preserve asset classification evidence from OpenLineage
- examples include facets that indicate model artifacts, checkpoints, storage backends, schema, or descriptive metadata
- future model views should continue to read from this facet layer rather than requiring a second lineage fact table

### `job_version_io_mapping`

- `id` UUID PK
- `job_version_id` UUID FK -> `job_versions.id`
- `dataset_id` UUID FK -> `datasets.id`
- `io_type` varchar not null

Constraints:

- unique (`job_version_id`, `dataset_id`, `io_type`)

## 7. Tool Dispatch Domain

These tables are not duplicates of lineage runs. They capture user intent and worker dispatch state inside the internal tool.

### `run_submissions`

One user-initiated launch request.

Columns:

- `id` UUID PK
- `workspace_id` UUID FK -> `workspaces.id`
- `submission_kind` varchar not null
- `recipe_version_id` UUID FK -> `recipe_versions.id` null
- `target_job_id` UUID FK -> `jobs.id` null
- `requested_by` varchar null
- `status` varchar not null default `PENDING`
- `parameters` jsonb not null default `'{}'::jsonb`
- `expected_output_namespace` varchar null
- `expected_output_name` varchar null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Recommended `submission_kind` values:

- `processing_pipeline`
- `training`
- `evaluation`

Notes:

- `target_job_id` is optional because the projected job may not exist before the first observed lineage event.
- although V1 focuses on Data-Juicer processing, keeping `training` and `evaluation` here reserves the API and schema shape for future model-related workflows.

### `run_submission_inputs`

Declared inputs chosen by a user at submission time.

Columns:

- `id` UUID PK
- `run_submission_id` UUID FK -> `run_submissions.id`
- `dataset_version_id` UUID FK -> `dataset_versions.id`
- `role` varchar null

Constraints:

- unique (`run_submission_id`, `dataset_version_id`, `role`)

Notes:

- V1 DJ workers should resolve input locations through the linked `dataset_versions.storage_uri`.

### `run_submission_outputs`

Declared expected outputs at submission time.

Columns:

- `id` UUID PK
- `run_submission_id` UUID FK -> `run_submissions.id`
- `dataset_id` UUID FK -> `datasets.id` null
- `dataset_namespace` varchar not null
- `dataset_name` varchar not null
- `declared_version` varchar null
- `storage_uri` text null
- `role` varchar null

Notes:

- This table stores declared output intent before an observed output dataset version is fully projected.
- `storage_uri` can be used by the DJ worker to materialize export targets in the generated config.

## 8. Execution Infrastructure Domain

### `workers`

- `id` UUID PK
- `workspace_id` UUID FK -> `workspaces.id`
- `worker_id` varchar unique not null
- `worker_type` varchar null
- `display_name` varchar null
- `labels` jsonb not null default `'{}'::jsonb`
- `capabilities` jsonb not null default `'{}'::jsonb`
- `max_concurrency` integer not null default `1`
- `status` varchar not null default `IDLE`
- `last_seen_at` timestamptz null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

### `worker_heartbeats`

- `id` UUID PK
- `worker_id` UUID FK -> `workers.id`
- `payload` jsonb not null default `'{}'::jsonb`
- `created_at` timestamptz not null default `now()`

### `tasks`

Claimable dispatch units created from run submissions.

Columns:

- `id` UUID PK
- `workspace_id` UUID FK -> `workspaces.id`
- `run_submission_id` UUID FK -> `run_submissions.id`
- `task_kind` varchar not null
- `status` varchar not null default `PENDING`
- `assigned_worker_id` UUID FK -> `workers.id` null
- `command` text null
- `execution_spec` jsonb not null default `'{}'::jsonb`
- `env_vars` jsonb not null default `'{}'::jsonb`
- `lease_expires_at` timestamptz null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

### `task_attempts`

Concrete worker attempts for one task.

Columns:

- `id` UUID PK
- `task_id` UUID FK -> `tasks.id`
- `worker_id` UUID FK -> `workers.id`
- `attempt_number` integer not null
- `lease_token` varchar not null
- `status` varchar not null default `CLAIMED`
- `started_at` timestamptz null
- `ended_at` timestamptz null
- `failure_reason` text null
- `openlineage_run_id` varchar null
- `mlflow_run_id` varchar null
- `created_at` timestamptz not null default `now()`
- `updated_at` timestamptz not null default `now()`

Constraints:

- unique (`task_id`, `attempt_number`)
- unique (`lease_token`)

Notes:

- For V1 DJ execution, `command` on `tasks` should be optional transitional compatibility only.
- The preferred contract is structured `execution_spec` plus dataset and recipe references, with the worker materializing a `dj-process --config ...` invocation locally.

### `task_attempt_runs`

Mapping between worker attempts and observed lineage runs.

Columns:

- `task_attempt_id` UUID FK -> `task_attempts.id`
- `run_id` UUID FK -> `runs.id`
- `relation_type` varchar not null default `PRIMARY`
- PK (`task_attempt_id`, `run_id`)

Recommended `relation_type` values:

- `PRIMARY`
- `CHILD`
- `DERIVED`

### `run_submission_runs`

Mapping between one tool submission and observed lineage runs.

Columns:

- `run_submission_id` UUID FK -> `run_submissions.id`
- `run_id` UUID FK -> `runs.id`
- `relation_type` varchar not null default `PRIMARY`
- PK (`run_submission_id`, `run_id`)

### `task_logs`

- `id` UUID PK
- `task_attempt_id` UUID FK -> `task_attempts.id`
- `stream` varchar not null
- `message` text not null
- `logged_at` timestamptz not null default `now()`

### `task_artifacts`

- `id` UUID PK
- `task_attempt_id` UUID FK -> `task_attempts.id`
- `artifact_type` varchar not null
- `name` varchar not null
- `uri` text not null
- `metadata` jsonb not null default `'{}'::jsonb`
- `created_at` timestamptz not null default `now()`

## 9. What Should Not Exist in the Target Schema

The following tables should not exist as independent runtime fact tables:

- `processing_runs`
- `processing_run_inputs`
- `processing_run_outputs`
- `training_runs`
- `training_run_inputs`
- `training_run_outputs`

Reason:

- their core semantics overlap with projected OpenLineage `runs`, `run_inputs`, and `run_outputs`
- they create two competing versions of runtime truth

## 10. Summary

The target schema keeps one runtime fact system and one dispatch system:

- OpenLineage projections own `jobs`, `runs`, inputs, outputs, and facets
- the tool owns recipe authoring, run submission, task dispatch, attempts, logs, and artifacts
- dataset-like and model-like assets should share the same `datasets` and `dataset_versions` backbone, with facet-derived classification and future product-specific filtered views
