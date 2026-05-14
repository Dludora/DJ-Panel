# Run Submission Spec

This document defines the current `dj-panel run submit` submission-spec direction.

## Processing

Processing now uses a spec-first model:

```bash
dj-panel run submit --workspace <workspace> --kind processing --spec ./process_spec.yaml
```

The first processing spec version is:

```yaml
kind: processing
name: demo-process-run
requestedBy: alice
process:
  dj_configs:
    mode: workspace_recipe
    name: lineage_base
    versionId: null
  datasets:
    inputs:
      - namespace: llm-team.datasets
        name: raw_sft
  extra_configs:
    export_path: /data/processed/train.jsonl
  env:
    OPENLINEAGE_URL: http://127.0.0.1:8000/api/v1/lineage
  timeoutSeconds: 7200
```

### `process.dj_configs`

Supported modes:

- `workspace_recipe`
  - `name` required
  - `versionId` optional; current version is used when omitted
- `local_file`
  - `path` required in the input spec
  - CLI resolves the local YAML file and embeds `recipeBody` into the payload sent to the backend

### `process.extra_configs`

- A DJ Panel-level parameter object
- For processing submissions it becomes the `parameters` payload stored on the submission
- When `process.datasets.inputs` is used, `extra_configs` must not contain `dataset` or `dataset_path`
- The DJ worker materializes the final panel-side `recipe.yaml` by merging:
  - `recipeBody`
  - submission `parameters`
  - the platform-injected DJ `work_dir`
- That materialized `recipe.yaml` is the panel input snapshot; DJ still writes its own runtime `cli.yaml` after parsing the job

### `process.datasets.inputs`

- Lets the processing spec reference platform-registered datasets by:
  - `namespace`
  - `name`
- The backend resolves each referenced dataset during submit time
- Resolution is strict:
  - the dataset must exist as `AssetKind.DATASET`
  - it must expose `facets.datajuicerInput.inputConfig`
- Each `inputConfig` must be a single DJ `dataset.configs[]` item, for example:

```yaml
type: local
path: /data/raw/train.jsonl
format: jsonl
```

- The backend combines all referenced inputs into:

```yaml
dataset:
  configs:
    - <dataset1 inputConfig>
    - <dataset2 inputConfig>
```

- This generated `dataset` object is written into submission `parameters`
- The worker does not resolve dataset references remotely; it only materializes the already-resolved payload

### `process.env`

- Execution-time environment variables injected into the generated task
- CLI-level `--env` and `--env-file` override keys in `process.env`

### `process.timeoutSeconds`

- Overrides the timeout used for the generated processing task
- For `workspace_recipe`, it overrides the selected recipe version timeout
- For `local_file`, it becomes the task timeout directly

## Current Worker Materialization

For processing tasks, the DJ worker now applies these fixed rules:

- `task_id == DJ job_id`
- `task_dir = <worker_workdir>/tasks/<task_id>`
- worker executes `dj-process` with:

```bash
dj-process --config <abs task_dir>/recipe.yaml --job_id <task_id>
```

- DJ final `work_dir` is aligned to that same `task_dir`
- panel-side files are:
  - `recipe.yaml`
  - `run.log`
- DJ runtime files are produced in the same task directory, for example:
  - `cli.yaml`
  - `events_*.jsonl`
  - `logs/`
  - `ckpt` / `checkpoints`
  - `processed.jsonl`
  - `metadata/`

## Run Lifecycle Helpers

The current run lifecycle helpers are:

- `dj-panel run list`
- `dj-panel run show`
- `dj-panel run resume`
- `dj-panel run cancel`

Current boundaries:

- `run resume`
  - only supports `FAILED` / `CANCELLED`
  - keeps the original `task_id`
  - creates a new attempt on the next claim so the same DJ `job_id/work_dir` can be reused
- `run cancel`
  - only supports `PENDING`
  - marks both the `run_submission` and derived `task` as `CANCELLED`
  - does not interrupt already-running worker processes
- `run logs`
  - not implemented yet

## Training / Evaluation

Training and evaluation remain command-spec based:

```yaml
name: qwen2-sft-v1
command: python train.py --config train.yaml
workdir: /mnt/team-repos/llm-trainer
env:
  MLFLOW_TRACKING_URI: http://127.0.0.1:5000
timeoutSeconds: 7200
inputs:
  - uri: /data/processed/train.jsonl
outputs:
  - uri: /data/models/qwen2-sft-v1
```

`--parameters` is still accepted for training/evaluation, but it is no longer part of the processing submission path.
