from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import (
    dataset_facets,
    dataset_versions,
    datasets,
    job_facets,
    job_version_io_mapping,
    job_versions,
    jobs,
    namespaces,
    run_facets,
    run_inputs,
    run_outputs,
    runs,
)
from app.models.db_rows import (
    DatasetRow,
    DatasetVersionRow,
    JobRow,
    JobVersionRow,
    NamespaceRow,
    RunRow,
)
from app.models.lineage_enums import DatasetLifecycleState, JobVersionIOType
from app.models.openlineage import DatasetRef, RunEventType


RUN_END_STATES = frozenset({RunEventType.COMPLETE, RunEventType.FAIL, RunEventType.ABORT})
RUN_START_STATES = frozenset({RunEventType.START, RunEventType.RUNNING})


class ProjectionRepository:
    def upsert_namespace(self, conn: Connection, name: str) -> NamespaceRow:
        existing = conn.execute(select(namespaces).where(namespaces.c.name == name)).mappings().first()
        now = datetime.now(timezone.utc)
        if existing:
            conn.execute(update(namespaces).where(namespaces.c.name == name).values(updated_at=now))
            return NamespaceRow.from_mapping({**dict(existing), 'updated_at': now})

        namespace = {
            'name': name,
            'created_at': now,
            'updated_at': now,
            'owner_name': '',
            'description': '',
            'is_hidden': False,
        }
        conn.execute(insert(namespaces).values(**namespace))
        return NamespaceRow.from_mapping(namespace)

    def upsert_job(self, conn: Connection, namespace: str, name: str, location: str | None = None) -> JobRow:
        existing = conn.execute(
            select(jobs).where(jobs.c.namespace == namespace, jobs.c.name == name)
        ).mappings().first()
        now = datetime.now(timezone.utc)
        if existing:
            conn.execute(
                update(jobs)
                .where(jobs.c.id == existing['id'])
                .values(location=location or existing['location'], updated_at=now)
            )
            return JobRow.from_mapping(
                {
                    **dict(existing),
                    'location': location or existing['location'],
                    'updated_at': now,
                }
            )

        job = {
            'id': str(uuid4()),
            'namespace': namespace,
            'name': name,
            'location': location,
            'current_job_version_id': None,
            'created_at': now,
            'updated_at': now,
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
        existing = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
        now = datetime.now(timezone.utc)
        started_at = existing['started_at'] if existing else None
        ended_at = existing['ended_at'] if existing else None

        if state in RUN_START_STATES and started_at is None:
            started_at = event_time or now
        if state in RUN_END_STATES:
            if started_at is None:
                started_at = event_time or now
            ended_at = event_time or now

        if existing:
            conn.execute(
                update(runs)
                .where(runs.c.id == existing['id'])
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
                    'job_id': job_id,
                    'event_time': event_time,
                    'state': state.value if state is not None else None,
                    'started_at': started_at,
                    'ended_at': ended_at,
                    'updated_at': now,
                }
            )

        run = {
            'id': str(uuid4()),
            'run_id': run_id,
            'job_id': job_id,
            'event_time': event_time,
            'state': state.value if state is not None else None,
            'started_at': started_at,
            'ended_at': ended_at,
            'job_version_id': None,
            'created_at': now,
            'updated_at': now,
        }
        conn.execute(insert(runs).values(**run))
        return RunRow.from_mapping(run)

    def upsert_dataset(self, conn: Connection, namespace: str, name: str) -> DatasetRow:
        existing = conn.execute(
            select(datasets).where(datasets.c.namespace == namespace, datasets.c.name == name)
        ).mappings().first()
        now = datetime.now(timezone.utc)
        if existing:
            conn.execute(update(datasets).where(datasets.c.id == existing['id']).values(updated_at=now))
            return DatasetRow.from_mapping({**dict(existing), 'updated_at': now})
        dataset = {
            'id': str(uuid4()),
            'namespace': namespace,
            'name': name,
            'created_at': now,
            'updated_at': now,
        }
        conn.execute(insert(datasets).values(**dataset))
        return DatasetRow.from_mapping(dataset)

    def replace_run_inputs(self, conn: Connection, run_db_id: str, dataset_ids: list[str]) -> None:
        conn.execute(delete(run_inputs).where(run_inputs.c.run_id == run_db_id))
        if dataset_ids:
            conn.execute(insert(run_inputs), [{'run_id': run_db_id, 'dataset_id': dataset_id} for dataset_id in dataset_ids])

    def replace_run_outputs(self, conn: Connection, run_db_id: str, dataset_ids: list[str]) -> None:
        conn.execute(delete(run_outputs).where(run_outputs.c.run_id == run_db_id))
        if dataset_ids:
            conn.execute(insert(run_outputs), [{'run_id': run_db_id, 'dataset_id': dataset_id} for dataset_id in dataset_ids])

    def upsert_job_facets(self, conn: Connection, job_id: str, facets: dict) -> None:
        self._upsert_facets(conn, job_facets, 'job_id', job_id, facets)

    def upsert_run_facets(self, conn: Connection, run_db_id: str, facets: dict) -> None:
        self._upsert_facets(conn, run_facets, 'run_id', run_db_id, facets)

    def upsert_dataset_facets(self, conn: Connection, dataset_id: str, dataset: DatasetRef) -> dict:
        payloads = dict(dataset.facets)
        if dataset.input_facets:
            payloads['_input_facets'] = dataset.input_facets
        if dataset.output_facets:
            payloads['_output_facets'] = dataset.output_facets
        self._upsert_facets(conn, dataset_facets, 'dataset_id', dataset_id, payloads)
        return payloads

    def compute_version_hash(self, job: JobRow, inputs: list[DatasetRow], outputs: list[DatasetRow]) -> str:
        payload = {
            'job_namespace': job.namespace,
            'job_name': job.name,
            'location': job.location,
            'inputs': sorted(f"{item.namespace}:{item.name}" for item in inputs),
            'outputs': sorted(f"{item.namespace}:{item.name}" for item in outputs),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()

    def compute_dataset_version(self, dataset: DatasetRow, run: RunRow, payloads: dict) -> str:
        snapshot = {
            'dataset_namespace': dataset.namespace,
            'dataset_name': dataset.name,
            'run_id': run.run_id,
            'payloads': payloads,
        }
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode('utf-8')).hexdigest()

    def upsert_dataset_version(
        self,
        conn: Connection,
        dataset: DatasetRow,
        run: RunRow,
        payloads: dict,
    ) -> DatasetVersionRow:
        version = self.compute_dataset_version(dataset, run, payloads)
        existing = conn.execute(
            select(dataset_versions).where(
                dataset_versions.c.dataset_id == dataset.id,
                dataset_versions.c.version == version,
            )
        ).mappings().first()
        fields = payloads.get('schema', {}).get('fields', [])
        lifecycle_state = (
            payloads.get('lifecycleState', {}).get('lifecycleState')
            or DatasetLifecycleState.ACTIVE.value
        )
        now = datetime.now(timezone.utc)
        if existing:
            conn.execute(
                update(dataset_versions)
                .where(dataset_versions.c.id == existing['id'])
                .values(fields=fields, facets=payloads, lifecycle_state=lifecycle_state, created_at=now)
            )
            return DatasetVersionRow.from_mapping(
                {
                    **dict(existing),
                    'fields': fields,
                    'facets': payloads,
                    'lifecycle_state': lifecycle_state,
                    'created_at': now,
                }
            )

        dataset_version = {
            'id': str(uuid4()),
            'dataset_id': dataset.id,
            'version': version,
            'created_by_run_id': run.id,
            'fields': fields,
            'facets': payloads,
            'lifecycle_state': lifecycle_state,
            'created_at': now,
        }
        conn.execute(insert(dataset_versions).values(**dataset_version))
        return DatasetVersionRow.from_mapping(dataset_version)

    def upsert_job_version(
        self,
        conn: Connection,
        job_id: str,
        version_hash: str,
        input_dataset_ids: list[str],
        output_dataset_ids: list[str],
    ) -> JobVersionRow:
        existing = conn.execute(
            select(job_versions).where(job_versions.c.job_id == job_id, job_versions.c.version_hash == version_hash)
        ).mappings().first()
        if existing:
            job_version = JobVersionRow.from_mapping(existing)
        else:
            job_version_values = {
                'id': str(uuid4()),
                'job_id': job_id,
                'version_hash': version_hash,
                'is_current': False,
                'created_at': datetime.now(timezone.utc),
            }
            conn.execute(insert(job_versions).values(**job_version_values))
            job_version = JobVersionRow.from_mapping(job_version_values)

        conn.execute(update(job_versions).where(job_versions.c.job_id == job_id).values(is_current=False))
        conn.execute(update(job_versions).where(job_versions.c.id == job_version.id).values(is_current=True))
        conn.execute(update(jobs).where(jobs.c.id == job_id).values(current_job_version_id=job_version.id))

        conn.execute(delete(job_version_io_mapping).where(job_version_io_mapping.c.job_version_id == job_version.id))
        rows = [
            {
                'id': str(uuid4()),
                'job_version_id': job_version.id,
                'dataset_id': dataset_id,
                'io_type': JobVersionIOType.INPUT.value,
            }
            for dataset_id in input_dataset_ids
        ] + [
            {
                'id': str(uuid4()),
                'job_version_id': job_version.id,
                'dataset_id': dataset_id,
                'io_type': JobVersionIOType.OUTPUT.value,
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

    def attach_run_to_job_version(self, conn: Connection, run_db_id: str, job_version_id: str) -> None:
        conn.execute(update(runs).where(runs.c.id == run_db_id).values(job_version_id=job_version_id))

    def _upsert_facets(self, conn: Connection, table, owner_key: str, owner_id: str, payloads: dict) -> None:
        now = datetime.now(timezone.utc)
        for facet_name, payload in payloads.items():
            existing = conn.execute(
                select(table).where(getattr(table.c, owner_key) == owner_id, table.c.facet_name == facet_name)
            ).mappings().first()
            if existing:
                conn.execute(
                    update(table)
                    .where(table.c.id == existing['id'])
                    .values(payload=payload, updated_at=now)
                )
            else:
                conn.execute(
                    insert(table).values(
                        id=str(uuid4()),
                        **{owner_key: owner_id},
                        facet_name=facet_name,
                        payload=payload,
                        updated_at=now,
                    )
                )
