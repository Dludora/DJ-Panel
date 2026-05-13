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
        "producer": "https://github.com/openai/dj-panel/examples/eval_sft_mlflow_lineage.py",
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
    parser.add_argument("--model-uri", required=True)
    parser.add_argument("--model-namespace", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--eval-dataset-uri", required=True)
    parser.add_argument("--eval-dataset-namespace", required=True)
    parser.add_argument("--eval-dataset-name", required=True)
    parser.add_argument("--report-uri", required=True)
    parser.add_argument("--report-namespace", required=True)
    parser.add_argument("--report-name", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    experiment_name = os.environ["MLFLOW_EXPERIMENT_NAME"]
    lineage_url = os.environ["DJ_PANEL_LINEAGE_URL"]

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=f"eval-{args.model_name}") as run:
        mlflow.set_tags(
            {
                "task": "sft-eval",
                "model_uri": args.model_uri,
                "eval_dataset_uri": args.eval_dataset_uri,
            }
        )

        emit_dataset_event(
            lineage_url=lineage_url,
            event_type="COMPLETE",
            namespace=args.model_namespace,
            name=args.model_name,
            facets={
                "dataSource": {"uri": args.model_uri, "name": "evaluated-model"},
                "djPanelAsset": {"assetKind": "MODEL", "role": "eval-input-model"},
            },
        )
        emit_dataset_event(
            lineage_url=lineage_url,
            event_type="COMPLETE",
            namespace=args.eval_dataset_namespace,
            name=args.eval_dataset_name,
            facets={
                "dataSource": {"uri": args.eval_dataset_uri, "name": "evaluation"},
                "djPanelAsset": {"assetKind": "DATASET", "role": "eval-input-dataset"},
            },
        )

        mlflow.log_metric("accuracy", 0.92)
        mlflow.log_metric("rougeL", 0.48)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "eval_report.json"
        report_path.write_text(
            json.dumps({"accuracy": 0.92, "rougeL": 0.48}, indent=2),
            encoding="utf-8",
        )
        mlflow.log_artifact(str(report_path), artifact_path="reports")

        emit_dataset_event(
            lineage_url=lineage_url,
            event_type="COMPLETE",
            namespace=args.report_namespace,
            name=args.report_name,
            facets={
                "dataSource": {"uri": args.report_uri, "name": "eval-report"},
                "djPanelAsset": {"assetKind": "EVAL_REPORT", "role": "eval-output"},
            },
        )

        print(f"mlflow_run_id={run.info.run_id}")


if __name__ == "__main__":
    main()
