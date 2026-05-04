from __future__ import annotations

from collections import deque
from enum import Enum

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.db.schema import assets, jobs
from app.models.api import Edge, LineageResponse, Node
from app.models.constant import JobVersionIOType
from app.repositories.lineage_query import LineageQueryRepository
from app.repositories.metadata import MetadataRepository


class NodeType(str, Enum):
    JOB = "job"
    DATASET = "dataset"


class GraphNodeType(str, Enum):
    JOB = "JOB"
    DATASET = "DATASET"


class LineageQueryService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.repo = LineageQueryRepository()
        self.metadata = MetadataRepository()

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
                    job = self.metadata.get_job_by_name(conn, current_ns, current_name)
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
                    job_version_id = self.repo.get_current_job_version_id(
                        conn, job_row[0]
                    )
                    if not job_version_id:
                        continue
                    input_ids, output_ids = self.repo.get_current_job_inputs_outputs(
                        conn, job_version_id
                    )
                    for dataset_id in input_ids:
                        dataset = self.metadata.get_dataset_by_id(conn, dataset_id)
                        if not dataset:
                            continue
                        self._ensure_dataset_node(nodes, dataset)
                        self._link(nodes, dataset, job, JobVersionIOType.INPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.DATASET.value,
                                    dataset.namespace,
                                    dataset.name,
                                    current_depth + 1,
                                )
                            )
                    for dataset_id in output_ids:
                        dataset = self.metadata.get_dataset_by_id(conn, dataset_id)
                        if not dataset:
                            continue
                        self._ensure_dataset_node(nodes, dataset)
                        self._link(nodes, dataset, job, JobVersionIOType.OUTPUT)
                        if current_depth < depth:
                            queue.append(
                                (
                                    NodeType.DATASET.value,
                                    dataset.namespace,
                                    dataset.name,
                                    current_depth + 1,
                                )
                            )
                else:
                    dataset = self.metadata.get_dataset_by_name(
                        conn, current_ns, current_name
                    )
                    if not dataset:
                        continue
                    self._ensure_dataset_node(nodes, dataset)
                    dataset_row = conn.execute(
                        select(assets.c.id).where(
                            assets.c.namespace == current_ns,
                            assets.c.name == current_name,
                        )
                    ).first()
                    if not dataset_row:
                        continue
                    producers, consumers = self.repo.get_current_jobs_for_dataset(
                        conn, dataset_row[0]
                    )
                    for job_id in producers:
                        job = self.metadata.get_job_by_id(conn, job_id)
                        if not job:
                            continue
                        self._ensure_job_node(nodes, job)
                        self._link(nodes, dataset, job, JobVersionIOType.OUTPUT)
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
                        job = self.metadata.get_job_by_id(conn, job_id)
                        if not job:
                            continue
                        self._ensure_job_node(nodes, job)
                        self._link(nodes, dataset, job, JobVersionIOType.INPUT)
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
            Node(id=node_id, type=GraphNodeType.DATASET.value, data=dataset.to_api_dict()),
        )

    @staticmethod
    def _link(
        nodes: dict[str, Node], dataset, job, io_type: JobVersionIOType
    ) -> None:
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
