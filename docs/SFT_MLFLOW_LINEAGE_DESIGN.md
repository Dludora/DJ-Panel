# SFT MLflow + Lineage Design

This note defines the first DJ Panel reference design for LLM SFT training and evaluation
with MLflow and `mlflow-openlineage`.

## Goals

We want one SFT train/eval flow that records:

- training input dataset
- validation / evaluation dataset
- output model
- checkpoint artifacts
- tokenizer / config artifacts
- evaluation report artifacts
- MLflow params, metrics, tags, and model registration events

## What `mlflow-openlineage` already covers

Current automatic OpenLineage coverage in `/Users/dludora/Code/mlflow-openlineage` is API-hook based:

- `mlflow.<flavor>.log_model`
- `mlflow.<flavor>.load_model`
- `mlflow.register_model`
- `mlflow.log_artifact`
- `mlflow.log_artifacts`
- `mlflow.artifacts.download_artifacts`

This is enough to emit lineage for:

- model outputs
- model loads
- registered models
- generic artifact logging and downloads

It does **not** fully describe the SFT dataflow by itself. Dataset lineage for train/val/eval
must still be made explicit by the script.

## Required environment/config

- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME`
- `MLFLOW_OPENLINEAGE_URL`
- `MLFLOW_OPENLINEAGE_NAMESPACE`
- `DJ_PANEL_LINEAGE_URL`

Recommended explicit inputs:

- `train_dataset_uri`
- `train_dataset_namespace`
- `train_dataset_name`
- `eval_dataset_uri`
- `eval_dataset_namespace`
- `eval_dataset_name`
- `model_output_uri`
- `model_namespace`
- `model_name`

## Reference train flow

1. Start or resume an MLflow run
2. Log train config, tokenizer name, base model name, dataset identifiers, and hyperparameters
3. Emit explicit dataset lineage for train / validation inputs before training starts
4. Run SFT training
5. Log metrics during training
6. Log checkpoints as artifacts
7. Log final model with `mlflow.<flavor>.log_model`
8. Optionally register the model with `mlflow.register_model`
9. Emit explicit output dataset/model lineage for the produced model package and reports

## Reference eval flow

1. Start or resume an MLflow run
2. Record evaluated model URI / registry URI
3. Emit explicit input lineage for:
   - evaluated model
   - evaluation dataset
4. Run inference/evaluation
5. Log aggregate metrics
6. Log per-sample report / tables / JSONL outputs as artifacts
7. Emit explicit output lineage for evaluation report artifacts

## Ownership split

- MLflow remains the source of metrics, params, tags, model logging, and model registry activity
- `mlflow-openlineage` emits API-level model/artifact lineage automatically
- SFT scripts must explicitly emit dataset-level lineage for train/validation/eval datasets
- DJ Panel should later provide helpers to standardize these explicit dataset/model declarations

## Example scripts

Reference examples live in:

- `/Users/dludora/Code/DJ-Panel/dj-panel-backend/docs/examples/train_sft_mlflow_lineage.py`
- `/Users/dludora/Code/DJ-Panel/dj-panel-backend/docs/examples/eval_sft_mlflow_lineage.py`
