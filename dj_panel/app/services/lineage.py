from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.engine import Engine

from dj_panel.app.db.schema import assets, jobs
from dj_panel.app.models.api import Edge, IngestionResponse, LineageResponse, Node
from dj_panel.app.models.constant import JobVersionIOType
from dj_panel.app.models.protocols.openlineage import (
    DatasetEvent,
    JobEvent,
    OpenLineageEvent,
    RunEvent,
    RunEventType,
)
from dj_panel.app.repositories.execution_links import ExecutionLinkRepository
from dj_panel.app.repositories.assets import AssetRepository
from dj_panel.app.repositories.lineage import LineageRepository
from dj_panel.app.repositories.tasks import TaskRepository


@dataclass(frozen=True)
class IngestionResult:
    projected: bool


class NodeType(str, Enum):
    JOB = "job"
    DATASET = "dataset"


class GraphNodeType(str, Enum):
    JOB = "JOB"
    DATASET = "DATASET"


class LineageService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.lineage_repo = LineageRepository()
        self.assets_repo = AssetRepository()
        self.execution_links_repo = ExecutionLinkRepository()
        self.task_repo = TaskRepository()

    def ingest(self, event: OpenLineageEvent, raw_payload: dict) -> IngestionResult:
        with self.engine.begin() as conn:
            self.lineage_repo.insert_raw_event(conn, event, raw_payload)
            if isinstance(event, DatasetEvent):
                self._ingest_dataset_event(conn, event)
                return IngestionResult(projected=True)

            if isinstance(event, JobEvent):
                self._ingest_job_event(conn, event)
                return IngestionResult(projected=True)

            if isinstance(event, RunEvent):
                self._ingest_run_event(conn, event)
                return IngestionResult(projected=True)

        return IngestionResult(projected=True)

    def _ingest_dataset_event(self, conn, event: DatasetEvent) -> None:
        self.lineage_repo.upsert_namespace(conn, event.dataset.namespace)
        asset_row = self.lineage_repo.upsert_dataset(
            conn, event.dataset.namespace, event.dataset.name
        )
        payloads = self.lineage_repo.build_dataset_facets_payload(event.dataset)
        self.lineage_repo.upsert_dataset_facets(conn, asset_row.id, payloads)
        version_row = self.assets_repo.upsert_asset_version(
            conn,
            asset_row,
            payloads,
            event_scope="DATASET_EVENT",
            created_by_run_id=None,
            set_current=True,
        )
        self.assets_repo.upsert_asset_facets(
            conn,
            asset_row.id,
            payloads,
            asset_version_id=version_row.id,
        )

    def _ingest_job_event(self, conn, event: JobEvent) -> None:
        self.lineage_repo.upsert_namespace(conn, event.job.namespace)
        for dataset in [*event.inputs, *event.outputs]:
            self.lineage_repo.upsert_namespace(conn, dataset.namespace)

        location = None
        if event.job.facets:
            location = event.job.facets.get("jobType", {}).get("processingType")

        job = self.lineage_repo.upsert_job(
            conn, event.job.namespace, event.job.name, location=location
        )
        input_assets = []
        output_assets = []

        for dataset_model in event.inputs:
            asset = self.lineage_repo.upsert_dataset(
                conn, dataset_model.namespace, dataset_model.name
            )
            input_assets.append(asset)
            payloads = self.lineage_repo.build_dataset_facets_payload(dataset_model)
            self.lineage_repo.upsert_dataset_facets(conn, asset.id, payloads)
            version_row = self.assets_repo.resolve_input_version_from_lineage(
                conn,
                asset,
                payloads,
                event_scope="JOB_EVENT_INPUT",
            )
            self.assets_repo.upsert_asset_facets(
                conn,
                asset.id,
                payloads,
                asset_version_id=version_row.id,
            )

        for dataset_model in event.outputs:
            asset = self.lineage_repo.upsert_dataset(
                conn, dataset_model.namespace, dataset_model.name
            )
            output_assets.append(asset)
            payloads = self.lineage_repo.build_dataset_facets_payload(dataset_model)
            self.lineage_repo.upsert_dataset_facets(conn, asset.id, payloads)
            current_version = self.assets_repo.get_current_asset_version_row(
                conn, asset.id
            )
            version_row = self.assets_repo.upsert_asset_version(
                conn,
                asset,
                payloads,
                event_scope="JOB_EVENT_OUTPUT",
                created_by_run_id=None,
                set_current=current_version is None,
            )
            self.assets_repo.upsert_asset_facets(
                conn,
                asset.id,
                payloads,
                asset_version_id=version_row.id,
            )

        version_hash = self.lineage_repo.compute_version_hash(
            job, input_assets, output_assets
        )
        job_version = self.lineage_repo.upsert_job_version(
            conn,
            job_id=job.id,
            version_hash=version_hash,
            input_dataset_ids=[item.id for item in input_assets],
            output_dataset_ids=[item.id for item in output_assets],
        )
        self.lineage_repo.upsert_job_facets(
            conn,
            job.id,
            event.job.facets,
            job_version_id=job_version.id,
        )

    def _ingest_run_event(self, conn, event: RunEvent) -> None:
        self.lineage_repo.upsert_namespace(conn, event.job.namespace)
        for dataset in [*event.inputs, *event.outputs]:
            self.lineage_repo.upsert_namespace(conn, dataset.namespace)

        location = None
        if event.job.facets:
            location = event.job.facets.get("jobType", {}).get("processingType")

        job = self.lineage_repo.upsert_job(
            conn, event.job.namespace, event.job.name, location=location
        )
        run = self.lineage_repo.upsert_run(
            conn,
            run_id=event.run.run_id,
            job_id=job.id,
            event_time=event.event_time,
            state=event.event_type,
        )
        self._link_pipeline_run_to_task(conn, event)
        self.lineage_repo.upsert_job_facets(
            conn,
            job.id,
            event.job.facets,
            run_id=run.id,
        )
        self.lineage_repo.upsert_run_facets(conn, run.id, event.run.facets)

        input_assets = [
            self.lineage_repo.upsert_dataset(conn, item.namespace, item.name)
            for item in event.inputs
        ]
        output_assets = [
            self.lineage_repo.upsert_dataset(conn, item.namespace, item.name)
            for item in event.outputs
        ]

        input_payloads = []
        output_payloads = []
        for model, asset in zip(event.inputs, input_assets):
            payloads = self.lineage_repo.build_dataset_facets_payload(model)
            self.lineage_repo.upsert_dataset_facets(conn, asset.id, payloads)
            input_payloads.append(payloads)
            version_row = self.assets_repo.resolve_input_version_from_lineage(
                conn,
                asset,
                payloads,
                run=run,
                event_scope="RUN_EVENT_INPUT",
            )
            self.assets_repo.upsert_asset_facets(
                conn,
                asset.id,
                payloads,
                asset_version_id=version_row.id,
                run_id=run.id,
            )
        for model, asset in zip(event.outputs, output_assets):
            payloads = self.lineage_repo.build_dataset_facets_payload(model)
            self.lineage_repo.upsert_dataset_facets(conn, asset.id, payloads)
            output_payloads.append(payloads)
            self.assets_repo.upsert_asset_facets(
                conn,
                asset.id,
                payloads,
                run_id=run.id,
            )
            if event.event_type == RunEventType.COMPLETE:
                version_row = self.assets_repo.upsert_asset_version(
                    conn,
                    asset,
                    payloads,
                    event_scope="RUN_EVENT_OUTPUT",
                    run=run,
                    created_by_run_id=run.id,
                    set_current=True,
                )
                self.assets_repo.attach_asset_facets_to_asset_version(
                    conn, run.id, asset.id, version_row.id
                )

        self.lineage_repo.replace_run_inputs(
            conn, run.id, [item.id for item in input_assets]
        )
        self.lineage_repo.replace_run_outputs(
            conn, run.id, [item.id for item in output_assets]
        )

        if event.event_type == RunEventType.COMPLETE:
            version_hash = self.lineage_repo.compute_version_hash(
                job, input_assets, output_assets
            )
            job_version = self.lineage_repo.upsert_job_version(
                conn,
                job_id=job.id,
                version_hash=version_hash,
                input_dataset_ids=[item.id for item in input_assets],
                output_dataset_ids=[item.id for item in output_assets],
            )
            self.lineage_repo.attach_run_to_job_version(conn, run.id, job_version.id)
            self.lineage_repo.attach_job_facets_to_job_version(
                conn, run.id, job_version.id
            )

    def _link_pipeline_run_to_task(self, conn, event: RunEvent) -> None:
        run_facets = event.run.facets or {}
        if "parent" in run_facets:
            return
        datajuicer_facet = run_facets.get("datajuicer") or {}
        task_id = datajuicer_facet.get("jobId")
        if not task_id:
            return
        task = self.task_repo.get_task_by_id(conn, task_id)
        if not task:
            return
        attempt_id = task.current_attempt_id
        self.execution_links_repo.upsert_execution_link(
            conn,
            run_submission_id=task.run_submission_id,
            task_id=task.id,
            task_attempt_id=attempt_id,
            openlineage_run_id=event.run.run_id,
        )
        if attempt_id:
            self.task_repo.set_attempt_openlineage_run_id(
                conn, attempt_id, event.run.run_id
            )

    def get_lineage(self, node_id: str, depth: int = 1) -> LineageResponse:
        node_type, namespace, name = self._parse_node_id(node_id)
        nodes: dict[str, Node] = {}
        visited: set[str] = set()
        queue = deque([(node_type, namespace, name, 0)])

        with self.engine.begin() as conn:
            while queue:
                current_type, current_ns, current_name, current_depth = queue.popleft()
                current_id = f"{current_type}:{current_ns}:{current_name}"
                if current_id in visited:
                    continue
                visited.add(current_id)

                if current_type == NodeType.JOB.value:
                    job = self.lineage_repo.get_job_by_name(
                        conn, current_ns, current_name
                    )
                    if not job:
                        continue
                    self._ensure_job_node(nodes, job)
                    job_row = conn.execute(
                        select(jobs.c.id).where(
                            jobs.c.namespace == current_ns, jobs.c.name == current_name
                        )
                    ).first()
                    if not job_row:
                        continue
                    job_version_id = self.lineage_repo.get_current_job_version_id(
                        conn, job_row[0]
                    )
                    if not job_version_id:
                        continue
                    input_ids, output_ids = (
                        self.lineage_repo.get_current_job_inputs_outputs(
                            conn, job_version_id
                        )
                    )
                    for asset_id in input_ids:
                        asset = self.assets_repo.get_asset_by_id(conn, asset_id)
                        if not asset:
                            continue
                        self._ensure_dataset_node(nodes, asset)
                        self._link(nodes, asset, job, JobVersionIOType.INPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.DATASET.value,
                                    asset.namespace,
                                    asset.name,
                                    current_depth + 1,
                                )
                            )
                    for asset_id in output_ids:
                        asset = self.assets_repo.get_asset_by_id(conn, asset_id)
                        if not asset:
                            continue
                        self._ensure_dataset_node(nodes, asset)
                        self._link(nodes, asset, job, JobVersionIOType.OUTPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.DATASET.value,
                                    asset.namespace,
                                    asset.name,
                                    current_depth + 1,
                                )
                            )
                else:
                    asset = self.assets_repo.get_asset_by_name(
                        conn, current_ns, current_name
                    )
                    if not asset:
                        continue
                    self._ensure_dataset_node(nodes, asset)
                    dataset_row = conn.execute(
                        select(assets.c.id).where(
                            assets.c.namespace == current_ns,
                            assets.c.name == current_name,
                        )
                    ).first()
                    if not dataset_row:
                        continue
                    producers, consumers = (
                        self.lineage_repo.get_current_jobs_for_dataset(
                            conn, dataset_row[0]
                        )
                    )
                    for job_id in producers:
                        job = self.lineage_repo.get_job_by_id(conn, job_id)
                        if not job:
                            continue
                        self._ensure_job_node(nodes, job)
                        self._link(nodes, asset, job, JobVersionIOType.OUTPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.JOB.value,
                                    job.namespace,
                                    job.name,
                                    current_depth + 1,
                                )
                            )
                    for job_id in consumers:
                        job = self.lineage_repo.get_job_by_id(conn, job_id)
                        if not job:
                            continue
                        self._ensure_job_node(nodes, job)
                        self._link(nodes, asset, job, JobVersionIOType.INPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.JOB.value,
                                    job.namespace,
                                    job.name,
                                    current_depth + 1,
                                )
                            )

        return LineageResponse(graph=list(nodes.values()))

    def list_lineage_events(self, limit: int) -> dict:
        with self.engine.begin() as conn:
            events, total_count = self.lineage_repo.list_recent(conn, limit=limit)
            return {"events": events, "totalCount": total_count}

    def list_namespaces(self) -> dict:
        with self.engine.begin() as conn:
            return self.lineage_repo.list_namespaces(conn).to_api_dict()

    def list_jobs(
        self,
        namespace: str | None,
        limit: int,
        offset: int,
        last_run_state: str | None = None,
    ) -> dict:
        with self.engine.begin() as conn:
            return self.lineage_repo.list_jobs(
                conn, namespace, limit, offset, last_run_state
            ).to_api_dict()

    def get_job(self, namespace: str, name: str) -> dict | None:
        with self.engine.begin() as conn:
            job = self.lineage_repo.get_job_by_name(conn, namespace, name)
            return job.to_api_dict() if job else None

    def get_runs(self, namespace: str, name: str, limit: int, offset: int) -> dict:
        with self.engine.begin() as conn:
            return self.lineage_repo.get_runs_for_job(
                conn, namespace, name, limit, offset
            ).to_api_dict()

    def get_run_or_job_facets(self, run_id: str, facet_type: str) -> dict:
        with self.engine.begin() as conn:
            return self.lineage_repo.get_facets_for_run(
                conn, run_id, facet_type
            ).to_api_dict()

    @staticmethod
    def _parse_node_id(node_id: str) -> tuple[str, str, str]:
        try:
            node_type, rest = node_id.split(":", 1)
            namespace, name = rest.rsplit(":", 1)
        except ValueError as exc:
            raise ValueError(
                "nodeId must look like job:namespace:name or dataset:namespace:name"
            ) from exc

        if node_type not in {NodeType.JOB.value, NodeType.DATASET.value}:
            raise ValueError(
                "nodeId must look like job:namespace:name or dataset:namespace:name"
            )
        return node_type, namespace, name

    @staticmethod
    def _ensure_job_node(nodes: dict[str, Node], job) -> None:
        node_id = f"{NodeType.JOB.value}:{job.namespace}:{job.name}"
        nodes.setdefault(
            node_id,
            Node(id=node_id, type=GraphNodeType.JOB.value, data=job.to_api_dict()),
        )

    @staticmethod
    def _ensure_dataset_node(nodes: dict[str, Node], dataset) -> None:
        node_id = f"{NodeType.DATASET.value}:{dataset.namespace}:{dataset.name}"
        nodes.setdefault(
            node_id,
            Node(
                id=node_id, type=GraphNodeType.DATASET.value, data=dataset.to_api_dict()
            ),
        )

    @staticmethod
    def _link(nodes: dict[str, Node], dataset, job, io_type: JobVersionIOType) -> None:
        dataset_id = f"{NodeType.DATASET.value}:{dataset.namespace}:{dataset.name}"
        job_id = f"{NodeType.JOB.value}:{job.namespace}:{job.name}"
        if io_type == JobVersionIOType.INPUT:
            edge = Edge(origin=dataset_id, destination=job_id)
            if edge not in nodes[job_id].in_edges:
                nodes[job_id].in_edges.append(edge)
            if edge not in nodes[dataset_id].out_edges:
                nodes[dataset_id].out_edges.append(edge)
        else:
            edge = Edge(origin=job_id, destination=dataset_id)
            if edge not in nodes[job_id].out_edges:
                nodes[job_id].out_edges.append(edge)
            if edge not in nodes[dataset_id].in_edges:
                nodes[dataset_id].in_edges.append(edge)
