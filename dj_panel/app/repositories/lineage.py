from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum

from sqlalchemy import delete, desc, func, insert, select, update
from sqlalchemy.engine import Connection

from dj_panel.app.db.rows import (
    AssetRow,
    JobRow,
    JobVersionRow,
    NamespaceRow,
    RunRow,
)
from dj_panel.app.db.schema import (
    assets,
    job_facets,
    job_version_io_mapping,
    job_versions,
    jobs,
    lineage_events,
    namespaces,
    run_facets,
    run_inputs,
    run_outputs,
    runs,
)
from dj_panel.app.models.api import (
    DatasetsResponse,
    JobModel,
    JobsResponse,
    JobVersionName,
    NamespaceModel,
    NamespaceName,
    NamespacesResponse,
    RunFacetsModel,
    RunModel,
    RunsResponse,
)
from dj_panel.app.models.constant import (
    AssetCatalogSource,
    JobProcessingType,
    JobVersionIOType,
    RUN_EVENT_TO_WEB_RUN_STATE,
    WebRunState,
)
from dj_panel.app.models.protocols.openlineage import (
    DatasetEvent,
    DatasetRef,
    JobEvent,
    OpenLineageEvent,
    RunEvent,
    RunEventType,
)
from dj_panel.app.utils.common_utils import new_id, utc_now


class StoredEventType(str, Enum):
    DATASET = "DATASET"
    JOB = "JOB"
    UNKNOWN = "UNKNOWN"


RUN_END_STATES = frozenset(
    {RunEventType.COMPLETE, RunEventType.FAIL, RunEventType.ABORT}
)
RUN_START_STATES = frozenset({RunEventType.START, RunEventType.RUNNING})


class LineageRepository:
    def insert_raw_event(
        self, conn: Connection, event: OpenLineageEvent, payload: dict
    ) -> str:
        event_id = new_id()
        if isinstance(event, RunEvent):
            event_type = (
                event.event_type.value
                if event.event_type is not None
                else StoredEventType.UNKNOWN.value
            )
        elif isinstance(event, DatasetEvent):
            event_type = StoredEventType.DATASET.value
        elif isinstance(event, JobEvent):
            event_type = StoredEventType.JOB.value
        else:
            event_type = StoredEventType.UNKNOWN.value

        conn.execute(
            insert(lineage_events).values(
                id=event_id,
                event_type=event_type,
                event_time=event.event_time or utc_now(),
                job_namespace=(
                    event.job.namespace
                    if isinstance(event, (RunEvent, JobEvent))
                    else None
                ),
                job_name=(
                    event.job.name if isinstance(event, (RunEvent, JobEvent)) else None
                ),
                run_id=event.run.run_id if isinstance(event, RunEvent) else None,
                producer=event.producer,
                payload=payload,
            )
        )
        return event_id

    def list_recent(self, conn: Connection, limit: int = 50) -> tuple[list[dict], int]:
        rows = (
            conn.execute(
                select(lineage_events)
                .order_by(lineage_events.c.created_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        total_count = conn.execute(
            select(func.count()).select_from(lineage_events)
        ).scalar_one()
        return [row["payload"] for row in rows], total_count

    def upsert_namespace(self, conn: Connection, name: str) -> NamespaceRow:
        existing = (
            conn.execute(select(namespaces).where(namespaces.c.name == name))
            .mappings()
            .first()
        )
        now = utc_now()
        if existing:
            conn.execute(
                update(namespaces)
                .where(namespaces.c.name == name)
                .values(updated_at=now)
            )
            return NamespaceRow.from_mapping({**dict(existing), "updated_at": now})

        namespace = {
            "name": name,
            "created_at": now,
            "updated_at": now,
            "owner_name": "",
            "description": "",
            "is_hidden": False,
        }
        conn.execute(insert(namespaces).values(**namespace))
        return NamespaceRow.from_mapping(namespace)

    def upsert_job(
        self,
        conn: Connection,
        namespace: str,
        name: str,
        location: str | None = None,
    ) -> JobRow:
        existing = (
            conn.execute(
                select(jobs).where(jobs.c.namespace == namespace, jobs.c.name == name)
            )
            .mappings()
            .first()
        )
        now = utc_now()
        if existing:
            conn.execute(
                update(jobs)
                .where(jobs.c.id == existing["id"])
                .values(location=location or existing["location"], updated_at=now)
            )
            return JobRow.from_mapping(
                {
                    **dict(existing),
                    "location": location or existing["location"],
                    "updated_at": now,
                }
            )

        job = {
            "id": new_id(),
            "namespace": namespace,
            "name": name,
            "location": location,
            "current_job_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(insert(jobs).values(**job))
        return JobRow.from_mapping(job)

    def upsert_run(
        self,
        conn: Connection,
        run_id: str,
        job_id: str,
        event_time: datetime | None,
        state: RunEventType | None,
    ) -> RunRow:
        existing = (
            conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
        )
        now = utc_now()
        started_at = existing["started_at"] if existing else None
        ended_at = existing["ended_at"] if existing else None

        if state in RUN_START_STATES and started_at is None:
            started_at = event_time or now
        if state in RUN_END_STATES:
            if started_at is None:
                started_at = event_time or now
            ended_at = event_time or now

        if existing:
            conn.execute(
                update(runs)
                .where(runs.c.id == existing["id"])
                .values(
                    job_id=job_id,
                    event_time=event_time,
                    state=state.value if state is not None else None,
                    started_at=started_at,
                    ended_at=ended_at,
                    updated_at=now,
                )
            )
            return RunRow.from_mapping(
                {
                    **dict(existing),
                    "job_id": job_id,
                    "event_time": event_time,
                    "state": state.value if state is not None else None,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "updated_at": now,
                }
            )

        run = {
            "id": new_id(),
            "run_id": run_id,
            "job_id": job_id,
            "event_time": event_time,
            "state": state.value if state is not None else None,
            "started_at": started_at,
            "ended_at": ended_at,
            "job_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(insert(runs).values(**run))
        return RunRow.from_mapping(run)

    def upsert_dataset(
        self,
        conn: Connection,
        namespace: str,
        name: str,
        asset_kind: str = "DATASET",
    ) -> AssetRow:
        existing = (
            conn.execute(
                select(assets).where(
                    assets.c.namespace == namespace, assets.c.name == name
                )
            )
            .mappings()
            .first()
        )
        now = utc_now()
        if existing:
            current_kind = existing.get("asset_kind") or "DATASET"
            next_kind = (
                asset_kind
                if current_kind == "DATASET" and asset_kind != "DATASET"
                else current_kind
            )
            next_source = (
                existing.get("catalog_source")
                or AssetCatalogSource.LINEAGE_DISCOVERED.value
            )
            conn.execute(
                update(assets)
                .where(assets.c.id == existing["id"])
                .values(
                    asset_kind=next_kind,
                    catalog_source=next_source,
                    updated_at=now,
                )
            )
            return AssetRow.from_mapping(
                {
                    **dict(existing),
                    "asset_kind": next_kind,
                    "catalog_source": next_source,
                    "updated_at": now,
                }
            )
        dataset = {
            "id": new_id(),
            "namespace": namespace,
            "name": name,
            "asset_kind": asset_kind,
            "catalog_source": AssetCatalogSource.LINEAGE_DISCOVERED.value,
            "created_at": now,
            "updated_at": now,
        }
        conn.execute(insert(assets).values(**dataset))
        return AssetRow.from_mapping(dataset)

    def replace_run_inputs(
        self, conn: Connection, run_db_id: str, dataset_ids: list[str]
    ) -> None:
        conn.execute(delete(run_inputs).where(run_inputs.c.run_id == run_db_id))
        if dataset_ids:
            conn.execute(
                insert(run_inputs),
                [
                    {"run_id": run_db_id, "asset_id": dataset_id}
                    for dataset_id in dataset_ids
                ],
            )

    def replace_run_outputs(
        self, conn: Connection, run_db_id: str, dataset_ids: list[str]
    ) -> None:
        conn.execute(delete(run_outputs).where(run_outputs.c.run_id == run_db_id))
        if dataset_ids:
            conn.execute(
                insert(run_outputs),
                [
                    {"run_id": run_db_id, "asset_id": dataset_id}
                    for dataset_id in dataset_ids
                ],
            )

    def upsert_job_facets(
        self,
        conn: Connection,
        job_id: str,
        facets: dict,
        *,
        job_version_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._upsert_job_facets(
            conn,
            job_id=job_id,
            facets=facets,
            job_version_id=job_version_id,
            run_id=run_id,
        )

    def upsert_run_facets(self, conn: Connection, run_db_id: str, facets: dict) -> None:
        self._upsert_facets(conn, run_facets, "run_id", run_db_id, facets)

    def build_dataset_facets_payload(self, dataset: DatasetRef) -> dict:
        payloads = dict(dataset.facets)
        if dataset.input_facets:
            payloads["_input_facets"] = dataset.input_facets
        if dataset.output_facets:
            payloads["_output_facets"] = dataset.output_facets
        return payloads

    def upsert_dataset_facets(
        self,
        conn: Connection,
        dataset_id: str,
        payloads: dict,
    ) -> dict:
        asset_kind = self.infer_asset_kind(payloads)
        current_kind = (
            conn.execute(
                select(assets.c.asset_kind).where(assets.c.id == dataset_id)
            ).scalar_one_or_none()
            or "DATASET"
        )
        next_kind = (
            asset_kind
            if current_kind == "DATASET" or asset_kind != "DATASET"
            else current_kind
        )
        conn.execute(
            update(assets).where(assets.c.id == dataset_id).values(asset_kind=next_kind)
        )
        return payloads

    def compute_version_hash(
        self, job: JobRow, inputs: list[AssetRow], outputs: list[AssetRow]
    ) -> str:
        payload = {
            "job_namespace": job.namespace,
            "job_name": job.name,
            "location": job.location,
            "inputs": sorted(f"{item.namespace}:{item.name}" for item in inputs),
            "outputs": sorted(f"{item.namespace}:{item.name}" for item in outputs),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def upsert_job_version(
        self,
        conn: Connection,
        job_id: str,
        version_hash: str,
        input_dataset_ids: list[str],
        output_dataset_ids: list[str],
    ) -> JobVersionRow:
        existing = (
            conn.execute(
                select(job_versions).where(
                    job_versions.c.job_id == job_id,
                    job_versions.c.version_hash == version_hash,
                )
            )
            .mappings()
            .first()
        )
        if existing:
            job_version = JobVersionRow.from_mapping(existing)
        else:
            job_version_values = {
                "id": new_id(),
                "job_id": job_id,
                "version_hash": version_hash,
                "is_current": False,
                "created_at": utc_now(),
            }
            conn.execute(insert(job_versions).values(**job_version_values))
            job_version = JobVersionRow.from_mapping(job_version_values)

        conn.execute(
            update(job_versions)
            .where(job_versions.c.job_id == job_id)
            .values(is_current=False)
        )
        conn.execute(
            update(job_versions)
            .where(job_versions.c.id == job_version.id)
            .values(is_current=True)
        )
        conn.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(current_job_version_id=job_version.id)
        )

        conn.execute(
            delete(job_version_io_mapping).where(
                job_version_io_mapping.c.job_version_id == job_version.id
            )
        )
        rows = [
            {
                "id": new_id(),
                "job_version_id": job_version.id,
                "asset_id": dataset_id,
                "io_type": JobVersionIOType.INPUT.value,
            }
            for dataset_id in input_dataset_ids
        ] + [
            {
                "id": new_id(),
                "job_version_id": job_version.id,
                "asset_id": dataset_id,
                "io_type": JobVersionIOType.OUTPUT.value,
            }
            for dataset_id in output_dataset_ids
        ]
        if rows:
            conn.execute(insert(job_version_io_mapping), rows)
        return JobVersionRow(
            id=job_version.id,
            job_id=job_version.job_id,
            version_hash=job_version.version_hash,
            is_current=True,
            created_at=job_version.created_at,
        )

    def attach_run_to_job_version(
        self, conn: Connection, run_db_id: str, job_version_id: str
    ) -> None:
        conn.execute(
            update(runs)
            .where(runs.c.id == run_db_id)
            .values(job_version_id=job_version_id)
        )

    def attach_job_facets_to_job_version(
        self, conn: Connection, run_db_id: str, job_version_id: str
    ) -> None:
        conn.execute(
            update(job_facets)
            .where(job_facets.c.run_id == run_db_id)
            .values(job_version_id=job_version_id, updated_at=utc_now())
        )

    def list_namespaces(self, conn: Connection) -> NamespacesResponse:
        rows = (
            conn.execute(select(namespaces).order_by(namespaces.c.name.asc()))
            .mappings()
            .all()
        )
        items = [self._namespace_model(NamespaceRow.from_mapping(row)) for row in rows]
        return NamespacesResponse(namespaces=items)

    def list_jobs(
        self,
        conn: Connection,
        namespace: str | None,
        limit: int,
        offset: int,
        last_run_state: str | None = None,
    ) -> JobsResponse:
        base_query = select(jobs.c.id)
        count_query = select(func.count()).select_from(jobs)
        if namespace:
            base_query = base_query.where(jobs.c.namespace == namespace)
            count_query = count_query.where(jobs.c.namespace == namespace)

        job_ids = [
            row[0]
            for row in conn.execute(
                base_query.order_by(jobs.c.updated_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        ]
        items = [self.get_job_by_id(conn, job_id) for job_id in job_ids]
        items = [item for item in items if item is not None]
        if last_run_state:
            items = [
                item
                for item in items
                if item.latest_run and item.latest_run.state == last_run_state
            ]
        total_count = conn.execute(count_query).scalar_one()
        if last_run_state:
            total_count = len(items)
        return JobsResponse(jobs=items, totalCount=total_count)

    def get_job_by_name(
        self, conn: Connection, namespace: str, name: str
    ) -> JobModel | None:
        row = (
            conn.execute(
                select(jobs).where(jobs.c.namespace == namespace, jobs.c.name == name)
            )
            .mappings()
            .first()
        )
        return self.get_job_by_id(conn, row["id"]) if row else None

    def get_job_by_id(self, conn: Connection, job_id: str) -> JobModel | None:
        row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
        if not row:
            return None
        job_row = JobRow.from_mapping(row)
        job_facets_payload = self._collect_current_job_facets(conn, job_row)
        inputs, outputs = self._current_job_assets(conn, job_row.id)
        latest_runs = self._job_runs(conn, job_row.id, limit=10, offset=0)
        latest_run = latest_runs[0] if latest_runs else None
        return JobModel(
            id=NamespaceName(namespace=job_row.namespace, name=job_row.name),
            type=self._job_type(job_facets_payload),
            name=job_row.name,
            createdAt=job_row.created_at,
            updatedAt=job_row.updated_at,
            inputs=[
                NamespaceName(namespace=item.namespace, name=item.name)
                for item in inputs
            ],
            outputs=[
                NamespaceName(namespace=item.namespace, name=item.name)
                for item in outputs
            ],
            namespace=job_row.namespace,
            location=job_row.location or "",
            description=self._description_from_facets(job_facets_payload),
            simpleName=job_row.name.split(".")[-1],
            latestRun=latest_run,
            latestRuns=latest_runs,
            tags=[],
            parentJobName=None,
            parentJobUuid=None,
        )

    def get_runs_for_job(
        self, conn: Connection, namespace: str, name: str, limit: int, offset: int
    ) -> RunsResponse:
        row = conn.execute(
            select(jobs.c.id).where(jobs.c.namespace == namespace, jobs.c.name == name)
        ).first()
        if not row:
            return RunsResponse(runs=[], totalCount=0)
        job_id = row[0]
        total_count = conn.execute(
            select(func.count()).select_from(runs).where(runs.c.job_id == job_id)
        ).scalar_one()
        return RunsResponse(
            runs=self._job_runs(conn, job_id, limit=limit, offset=offset),
            totalCount=total_count,
        )

    def get_facets_for_run(
        self, conn: Connection, run_public_id: str, facet_type: str
    ) -> RunFacetsModel:
        run_row = (
            conn.execute(select(runs).where(runs.c.run_id == run_public_id))
            .mappings()
            .first()
        )
        if not run_row:
            return RunFacetsModel(runId=run_public_id, facets={})
        typed_run = RunRow.from_mapping(run_row)
        if facet_type == "job":
            facets_payload = self._collect_job_facets_for_run(conn, typed_run)
        else:
            facets_payload = self._collect_facets(
                conn, run_facets, "run_id", typed_run.id
            )
        return RunFacetsModel(runId=run_public_id, facets=facets_payload)

    def get_current_job_inputs_outputs(
        self, conn: Connection, job_version_id: str
    ) -> tuple[list[str], list[str]]:
        rows = (
            conn.execute(
                select(
                    job_version_io_mapping.c.asset_id, job_version_io_mapping.c.io_type
                ).where(job_version_io_mapping.c.job_version_id == job_version_id)
            )
            .mappings()
            .all()
        )
        inputs = [
            row["asset_id"]
            for row in rows
            if row["io_type"] == JobVersionIOType.INPUT.value
        ]
        outputs = [
            row["asset_id"]
            for row in rows
            if row["io_type"] == JobVersionIOType.OUTPUT.value
        ]
        return inputs, outputs

    def get_current_job_version_id(self, conn: Connection, job_id: str) -> str | None:
        row = conn.execute(
            select(job_versions.c.id).where(
                job_versions.c.job_id == job_id, job_versions.c.is_current.is_(True)
            )
        ).first()
        return row[0] if row else None

    def get_current_jobs_for_dataset(
        self, conn: Connection, dataset_id: str
    ) -> tuple[list[str], list[str]]:
        rows = (
            conn.execute(
                select(job_versions.c.job_id, job_version_io_mapping.c.io_type)
                .select_from(
                    job_versions.join(
                        job_version_io_mapping,
                        job_versions.c.id == job_version_io_mapping.c.job_version_id,
                    )
                )
                .where(
                    job_versions.c.is_current.is_(True),
                    job_version_io_mapping.c.asset_id == dataset_id,
                )
            )
            .mappings()
            .all()
        )
        consumers = [
            row["job_id"]
            for row in rows
            if row["io_type"] == JobVersionIOType.INPUT.value
        ]
        producers = [
            row["job_id"]
            for row in rows
            if row["io_type"] == JobVersionIOType.OUTPUT.value
        ]
        return producers, consumers

    @staticmethod
    def infer_asset_kind(payloads: dict) -> str:
        if not payloads:
            return "DATASET"

        for facet_name in payloads:
            normalized = facet_name.lower()
            if "mlflow_model" in normalized or normalized in {"model", "modelversion"}:
                return "MODEL"
            if "checkpoint" in normalized:
                return "CHECKPOINT"
            if "eval" in normalized and "report" in normalized:
                return "EVAL_REPORT"

        for payload in payloads.values():
            if isinstance(payload, dict):
                values = [
                    str(value).lower()
                    for value in payload.values()
                    if isinstance(value, (str, int, float, bool))
                ]
                joined = " ".join(values)
                if "model" in joined:
                    return "MODEL"
                if "checkpoint" in joined:
                    return "CHECKPOINT"
        return "DATASET"

    @staticmethod
    def _namespace_model(namespace_row: NamespaceRow) -> NamespaceModel:
        return NamespaceModel(
            name=namespace_row.name,
            createdAt=namespace_row.created_at,
            updatedAt=namespace_row.updated_at,
            ownerName=namespace_row.owner_name,
            description=namespace_row.description,
            isHidden=namespace_row.is_hidden,
        )

    def _job_runs(
        self, conn: Connection, job_id: str, limit: int, offset: int
    ) -> list[RunModel]:
        rows = (
            conn.execute(
                select(runs)
                .where(runs.c.job_id == job_id)
                .order_by(
                    desc(
                        func.coalesce(
                            runs.c.ended_at,
                            runs.c.started_at,
                            runs.c.event_time,
                            runs.c.created_at,
                        )
                    )
                )
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        return [self._run_model(conn, RunRow.from_mapping(row)) for row in rows]

    def _run_model(self, conn: Connection, run_row: RunRow) -> RunModel:
        run_facets_payload = self._collect_facets(
            conn, run_facets, "run_id", run_row.id
        )
        job_row = (
            conn.execute(select(jobs).where(jobs.c.id == run_row.job_id))
            .mappings()
            .first()
        )
        job_version_name = JobVersionName(
            name=job_row["name"] if job_row else "",
            namespace=job_row["namespace"] if job_row else "",
            version="",
        )
        if run_row.job_version_id:
            version_row = conn.execute(
                select(job_versions.c.version_hash).where(
                    job_versions.c.id == run_row.job_version_id
                )
            ).first()
            if version_row:
                job_version_name = JobVersionName(
                    name=job_version_name.name,
                    namespace=job_version_name.namespace,
                    version=version_row[0],
                )
        started_at = run_row.started_at or run_row.event_time or run_row.created_at
        ended_at = run_row.ended_at
        duration_ms = 0
        if started_at and ended_at:
            duration_ms = max(int((ended_at - started_at).total_seconds() * 1000), 0)
        args: dict[str, str] = {}
        execution_parameters = run_facets_payload.get("execution_parameters", {})
        if isinstance(execution_parameters, dict):
            args = self._normalize_run_args(execution_parameters.get("parameters"))
        return RunModel(
            id=run_row.run_id,
            createdAt=run_row.created_at,
            updatedAt=run_row.updated_at,
            nominalStartTime=started_at,
            nominalEndTime=ended_at,
            state=self._web_run_state(run_row.state).value,
            jobVersion=job_version_name,
            startedAt=started_at,
            endedAt=ended_at,
            durationMs=duration_ms,
            args=args,
            facets=run_facets_payload,
        )

    def _current_job_assets(
        self, conn: Connection, job_id: str
    ) -> tuple[list[AssetRow], list[AssetRow]]:
        rows = (
            conn.execute(
                select(assets, job_version_io_mapping.c.io_type)
                .select_from(
                    job_versions.join(
                        job_version_io_mapping,
                        job_versions.c.id == job_version_io_mapping.c.job_version_id,
                    ).join(assets, assets.c.id == job_version_io_mapping.c.asset_id)
                )
                .where(
                    job_versions.c.job_id == job_id, job_versions.c.is_current.is_(True)
                )
            )
            .mappings()
            .all()
        )
        inputs = [
            AssetRow.from_mapping(row)
            for row in rows
            if row["io_type"] == JobVersionIOType.INPUT.value
        ]
        outputs = [
            AssetRow.from_mapping(row)
            for row in rows
            if row["io_type"] == JobVersionIOType.OUTPUT.value
        ]
        return inputs, outputs

    @staticmethod
    def _collect_facets(conn: Connection, table, owner_key: str, owner_id: str) -> dict:
        rows = conn.execute(
            select(table.c.facet_name, table.c.payload).where(
                getattr(table.c, owner_key) == owner_id
            )
        ).all()
        return {facet_name: payload for facet_name, payload in rows}

    def _collect_current_job_facets(self, conn: Connection, job_row: JobRow) -> dict:
        if job_row.current_job_version_id:
            rows = conn.execute(
                select(job_facets.c.facet_name, job_facets.c.payload).where(
                    job_facets.c.job_version_id == job_row.current_job_version_id
                )
            ).all()
            if rows:
                return {facet_name: payload for facet_name, payload in rows}
        return {}

    def _collect_job_facets_for_run(self, conn: Connection, run_row: RunRow) -> dict:
        rows = conn.execute(
            select(job_facets.c.facet_name, job_facets.c.payload).where(
                job_facets.c.run_id == run_row.id
            )
        ).all()
        if rows:
            return {facet_name: payload for facet_name, payload in rows}

        if run_row.job_version_id:
            rows = conn.execute(
                select(job_facets.c.facet_name, job_facets.c.payload).where(
                    job_facets.c.job_version_id == run_row.job_version_id
                )
            ).all()
            if rows:
                return {facet_name: payload for facet_name, payload in rows}
        return {}

    @staticmethod
    def _job_type(facets_payload: dict) -> str:
        processing_type = facets_payload.get("jobType", {}).get("processingType")
        if processing_type in {item.value for item in JobProcessingType}:
            return processing_type
        return JobProcessingType.BATCH.value

    @staticmethod
    def _description_from_facets(facets_payload: dict) -> str:
        documentation = facets_payload.get("documentation", {})
        if isinstance(documentation, dict):
            description = documentation.get("description")
            if isinstance(description, str):
                return description
        return ""

    @staticmethod
    def _normalize_run_args(raw_args) -> dict[str, str]:
        if isinstance(raw_args, dict):
            return {
                str(key): "" if value is None else str(value)
                for key, value in raw_args.items()
            }
        if isinstance(raw_args, list):
            normalized: dict[str, str] = {}
            for item in raw_args:
                if not isinstance(item, dict):
                    continue
                key = item.get("key")
                if key is None:
                    continue
                normalized[str(key)] = (
                    "" if item.get("value") is None else str(item.get("value"))
                )
            return normalized
        return {}

    @staticmethod
    def _web_run_state(run_state: str | None) -> WebRunState:
        if not run_state:
            return WebRunState.NEW
        try:
            normalized_state = RunEventType(run_state.upper())
        except ValueError:
            return WebRunState.NEW
        return RUN_EVENT_TO_WEB_RUN_STATE.get(normalized_state, WebRunState.NEW)

    def _upsert_facets(
        self, conn: Connection, table, owner_key: str, owner_id: str, payloads: dict
    ) -> None:
        now = utc_now()
        for facet_name, payload in payloads.items():
            existing = (
                conn.execute(
                    select(table).where(
                        getattr(table.c, owner_key) == owner_id,
                        table.c.facet_name == facet_name,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                conn.execute(
                    update(table)
                    .where(table.c.id == existing["id"])
                    .values(payload=payload, updated_at=now)
                )
            else:
                conn.execute(
                    insert(table).values(
                        id=new_id(),
                        **{owner_key: owner_id},
                        facet_name=facet_name,
                        payload=payload,
                        updated_at=now,
                    )
                )

    def _upsert_job_facets(
        self,
        conn: Connection,
        *,
        job_id: str,
        facets: dict,
        job_version_id: str | None,
        run_id: str | None,
    ) -> None:
        now = utc_now()
        for facet_name, payload in facets.items():
            query = select(job_facets).where(
                job_facets.c.job_id == job_id,
                job_facets.c.facet_name == facet_name,
            )
            if run_id is None:
                query = query.where(job_facets.c.run_id.is_(None))
            else:
                query = query.where(job_facets.c.run_id == run_id)

            if job_version_id is None:
                query = query.where(job_facets.c.job_version_id.is_(None))
            else:
                query = query.where(job_facets.c.job_version_id == job_version_id)

            existing = conn.execute(query).mappings().first()
            values = {
                "payload": payload,
                "updated_at": now,
                "job_version_id": job_version_id,
                "run_id": run_id,
            }
            if existing:
                conn.execute(
                    update(job_facets)
                    .where(job_facets.c.id == existing["id"])
                    .values(**values)
                )
            else:
                conn.execute(
                    insert(job_facets).values(
                        id=new_id(),
                        job_id=job_id,
                        facet_name=facet_name,
                        **values,
                    )
                )
