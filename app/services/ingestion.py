from __future__ import annotations

from sqlalchemy.engine import Engine

from app.models.api.ingestion import IngestionResult
from app.models.schemas.openlineage import (
    DatasetEvent,
    JobEvent,
    OpenLineageEvent,
    RunEvent,
    RunEventType,
)
from app.repositories.lineage_events import LineageEventRepository
from app.repositories.projection import ProjectionRepository


class IngestionService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.events = LineageEventRepository()
        self.projection = ProjectionRepository()

    def ingest(self, event: OpenLineageEvent, raw_payload: dict) -> IngestionResult:
        with self.engine.begin() as conn:
            self.events.insert_raw_event(conn, event, raw_payload)
            if isinstance(event, DatasetEvent):
                self.projection.upsert_namespace(conn, event.dataset.namespace)
                dataset = self.projection.upsert_dataset(
                    conn, event.dataset.namespace, event.dataset.name
                )
                self.projection.upsert_dataset_facets(conn, dataset.id, event.dataset)
                return IngestionResult(projected=True)

            elif isinstance(event, JobEvent):
                self.projection.upsert_namespace(conn, event.job.namespace)
                for dataset in [*event.inputs, *event.outputs]:
                    self.projection.upsert_namespace(conn, dataset.namespace)

                location = None
                if event.job.facets:
                    location = event.job.facets.get("jobType", {}).get("processingType")

                job = self.projection.upsert_job(
                    conn, event.job.namespace, event.job.name, location=location
                )
                self.projection.upsert_job_facets(conn, job.id, event.job.facets)

                for dataset_model in [*event.inputs, *event.outputs]:
                    dataset = self.projection.upsert_dataset(
                        conn, dataset_model.namespace, dataset_model.name
                    )
                    self.projection.upsert_dataset_facets(conn, dataset.id, dataset_model)

                return IngestionResult(projected=True)

            self.projection.upsert_namespace(conn, event.job.namespace)
            for dataset in [*event.inputs, *event.outputs]:
                self.projection.upsert_namespace(conn, dataset.namespace)

            location = None
            if event.job.facets:
                location = event.job.facets.get("jobType", {}).get("processingType")

            job = self.projection.upsert_job(
                conn, event.job.namespace, event.job.name, location=location
            )
            run = self.projection.upsert_run(
                conn,
                run_id=event.run.run_id,
                job_id=job.id,
                event_time=event.event_time,
                state=event.event_type,
            )
            self.projection.upsert_job_facets(conn, job.id, event.job.facets)
            self.projection.upsert_run_facets(conn, run.id, event.run.facets)

            input_datasets = [
                self.projection.upsert_dataset(conn, item.namespace, item.name)
                for item in event.inputs
            ]
            output_datasets = [
                self.projection.upsert_dataset(conn, item.namespace, item.name)
                for item in event.outputs
            ]

            input_payloads = []
            output_payloads = []
            for model, dataset in zip(event.inputs, input_datasets):
                input_payloads.append(
                    self.projection.upsert_dataset_facets(conn, dataset.id, model)
                )
            for model, dataset in zip(event.outputs, output_datasets):
                output_payloads.append(
                    self.projection.upsert_dataset_facets(conn, dataset.id, model)
                )

            self.projection.replace_run_inputs(
                conn, run.id, [item.id for item in input_datasets]
            )
            self.projection.replace_run_outputs(
                conn, run.id, [item.id for item in output_datasets]
            )

            if event.event_type == RunEventType.COMPLETE:
                version_hash = self.projection.compute_version_hash(
                    job, input_datasets, output_datasets
                )
                job_version = self.projection.upsert_job_version(
                    conn,
                    job_id=job.id,
                    version_hash=version_hash,
                    input_dataset_ids=[item.id for item in input_datasets],
                    output_dataset_ids=[item.id for item in output_datasets],
                )
                self.projection.attach_run_to_job_version(conn, run.id, job_version.id)
                for dataset, payloads in zip(output_datasets, output_payloads):
                    self.projection.upsert_dataset_version(conn, dataset, run, payloads)

        return IngestionResult(projected=True)
