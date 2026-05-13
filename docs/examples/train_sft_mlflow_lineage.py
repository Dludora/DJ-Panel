from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import mlflow
import requests


def emit_dataset_event(
    *,
    lineage_url: str,
    event_type: str,
    namespace: str,
    name: str,
    facets: dict[str, Any],
) -> None:
    payload = {
        "eventType": event_type,
        "eventTime": "2026-01-01T00:00:00Z",
        "producer": "https://github.com/openai/dj-panel/examples/train_sft_mlflow_lineage.py",
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/DatasetEvent",
        "dataset": {
            "namespace": namespace,
            "name": name,
            "facets": facets,
        },
    }
    requests.post(lineage_url, json=payload, timeout=30).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-dataset-uri", required=True)
    parser.add_argument("--train-dataset-namespace", required=True)
    parser.add_argument("--train-dataset-name", required=True)
    parser.add_argument("--val-dataset-uri", default=None)
    parser.add_argument("--val-dataset-namespace", default=None)
    parser.add_argument("--val-dataset-name", default=None)
    parser.add_argument("--model-output-uri", required=True)
    parser.add_argument("--model-namespace", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    args = parser.parse_args()

    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    experiment_name = os.environ["MLFLOW_EXPERIMENT_NAME"]
    lineage_url = os.environ["DJ_PANEL_LINEAGE_URL"]

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=f"sft-{args.model_name}") as run:
        mlflow.set_tags(
            {
                "task": "sft-train",
                "base_model": args.base_model,
                "train_dataset_uri": args.train_dataset_uri,
            }
        )
        mlflow.log_params(
            {
                "base_model": args.base_model,
                "epochs": args.epochs,
                "learning_rate": args.learning_rate,
                "train_dataset_uri": args.train_dataset_uri,
                "val_dataset_uri": args.val_dataset_uri,
            }
        )

        emit_dataset_event(
            lineage_url=lineage_url,
            event_type="COMPLETE",
            namespace=args.train_dataset_namespace,
            name=args.train_dataset_name,
            facets={
                "dataSource": {"uri": args.train_dataset_uri, "name": "training"},
                "djPanelAsset": {"assetKind": "DATASET", "role": "train-input"},
            },
        )
        if args.val_dataset_uri and args.val_dataset_namespace and args.val_dataset_name:
            emit_dataset_event(
                lineage_url=lineage_url,
                event_type="COMPLETE",
                namespace=args.val_dataset_namespace,
                name=args.val_dataset_name,
                facets={
                    "dataSource": {"uri": args.val_dataset_uri, "name": "validation"},
                    "djPanelAsset": {"assetKind": "DATASET", "role": "validation-input"},
                },
            )

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        config_path = output_dir / "train_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "base_model": args.base_model,
                    "epochs": args.epochs,
                    "learning_rate": args.learning_rate,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        mlflow.log_metric("train_loss", 0.123, step=1)
        mlflow.log_metric("eval_loss", 0.111, step=1)
        mlflow.log_artifact(str(config_path), artifact_path="configs")

        # Replace with the actual flavor-specific mlflow.<flavor>.log_model call when available.
        model_dir = output_dir / "final-model"
        model_dir.mkdir(exist_ok=True)
        (model_dir / "README.txt").write_text("placeholder SFT model", encoding="utf-8")
        mlflow.log_artifacts(str(model_dir), artifact_path="model")

        emit_dataset_event(
            lineage_url=lineage_url,
            event_type="COMPLETE",
            namespace=args.model_namespace,
            name=args.model_name,
            facets={
                "dataSource": {"uri": args.model_output_uri, "name": "model-output"},
                "djPanelAsset": {"assetKind": "MODEL", "role": "train-output"},
            },
        )

        print(f"mlflow_run_id={run.info.run_id}")


if __name__ == "__main__":
    main()
