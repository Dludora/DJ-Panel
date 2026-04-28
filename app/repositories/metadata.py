from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.engine import Connection

from app.db.schema import (
    asset_facets,
    asset_versions,
    assets,
    job_facets,
    job_version_io_mapping,
    job_versions,
    jobs,
    namespaces,
    run_facets,
    runs,
)
from app.db.rows.lineage import AssetRow, AssetVersionRow, JobRow, NamespaceRow, RunRow
from app.models.types.lineage import (
    DatasetLifecycleState,
    JobProcessingType,
    JobVersionIOType,
    RUN_EVENT_TO_WEB_RUN_STATE,
    WebRunState,
)
from app.models.api.metadata import (
    DatasetModel,
    DatasetVersionModel,
    DatasetVersionsResponse,
    DatasetsResponse,
    FieldModel,
    JobModel,
    JobsResponse,
    JobVersionName,
    NamespaceModel,
    NamespaceName,
    NamespacesResponse,
    RunFacetsModel,
    RunModel,
    RunsResponse,
    TagModel,
    TagsResponse,
    VersionedNamespaceName,
)
from app.models.schemas.openlineage import RunEventType


class MetadataRepository:
    def list_tags(self, conn: Connection) -> TagsResponse:
        return TagsResponse(tags=[])

    def upsert_tag(self, conn: Connection, name: str, description: str) -> TagModel:
        return TagModel(name=name, description=description)

    def list_namespaces(self, conn: Connection) -> NamespacesResponse:
        rows = conn.execute(select(namespaces).order_by(namespaces.c.name.asc())).mappings().all()
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
                base_query.order_by(jobs.c.updated_at.desc()).limit(limit).offset(offset)
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
            total_count = len(
                [
                    1
                    for row in conn.execute(base_query.order_by(jobs.c.updated_at.desc())).all()
                    if (
                        lambda job: job and job.latest_run and job.latest_run.state == last_run_state
                    )(self.get_job_by_id(conn, row[0]))
                ]
            )
        return JobsResponse(jobs=items, totalCount=total_count)

    def list_datasets(self, conn: Connection, namespace: str, limit: int, offset: int) -> DatasetsResponse:
        base_query = select(assets.c.id).where(assets.c.namespace == namespace)
        total_count = conn.execute(
            select(func.count()).select_from(assets).where(assets.c.namespace == namespace)
        ).scalar_one()
        dataset_ids = [
            row[0]
            for row in conn.execute(
                base_query.order_by(assets.c.updated_at.desc()).limit(limit).offset(offset)
            ).all()
        ]
        items = [self.get_dataset_by_id(conn, dataset_id) for dataset_id in dataset_ids]
        return DatasetsResponse(
            datasets=[item for item in items if item is not None],
            totalCount=total_count,
        )

    def get_job_by_name(self, conn: Connection, namespace: str, name: str) -> JobModel | None:
        row = conn.execute(
            select(jobs).where(jobs.c.namespace == namespace, jobs.c.name == name)
        ).mappings().first()
        return self.get_job_by_id(conn, row['id']) if row else None

    def get_job_by_id(self, conn: Connection, job_id: str) -> JobModel | None:
        row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().first()
        if not row:
            return None
        job_row = JobRow.from_mapping(row)
        job_facets_payload = self._collect_facets(conn, job_facets, 'job_id', job_row.id)
        inputs, outputs = self._current_job_datasets(conn, job_row.id)
        latest_runs = self._job_runs(conn, job_row.id, limit=10, offset=0)
        latest_run = latest_runs[0] if latest_runs else None
        return JobModel(
            id=NamespaceName(namespace=job_row.namespace, name=job_row.name),
            type=self._job_type(job_facets_payload),
            name=job_row.name,
            createdAt=job_row.created_at,
            updatedAt=job_row.updated_at,
            inputs=[NamespaceName(namespace=item.namespace, name=item.name) for item in inputs],
            outputs=[NamespaceName(namespace=item.namespace, name=item.name) for item in outputs],
            namespace=job_row.namespace,
            location=job_row.location or '',
            description=self._description_from_facets(job_facets_payload),
            simpleName=job_row.name.split('.')[-1],
            latestRun=latest_run,
            latestRuns=latest_runs,
            tags=[],
            parentJobName=None,
            parentJobUuid=None,
        )

    def get_dataset_by_name(self, conn: Connection, namespace: str, name: str) -> DatasetModel | None:
        row = conn.execute(
            select(assets).where(assets.c.namespace == namespace, assets.c.name == name)
        ).mappings().first()
        return self.get_dataset_by_id(conn, row['id']) if row else None

    def get_dataset_by_id(self, conn: Connection, dataset_id: str) -> DatasetModel | None:
        row = conn.execute(select(assets).where(assets.c.id == dataset_id)).mappings().first()
        if not row:
            return None
        dataset_row = AssetRow.from_mapping(row)
        dataset_facets_payload = self._collect_facets(conn, asset_facets, 'asset_id', dataset_row.id)
        latest_version = self._latest_dataset_version(conn, dataset_row.id)
        fields = self._dataset_fields(dataset_facets_payload, latest_version)
        updated_at = latest_version.created_at if latest_version else dataset_row.updated_at
        return DatasetModel(
            id=NamespaceName(namespace=dataset_row.namespace, name=dataset_row.name),
            type='DB_TABLE',
            assetKind=dataset_row.asset_kind,
            name=dataset_row.name,
            physicalName=f'{dataset_row.namespace}.{dataset_row.name}',
            createdAt=dataset_row.created_at,
            updatedAt=updated_at,
            namespace=dataset_row.namespace,
            sourceName='default',
            fields=fields,
            tags=[],
            lastModifiedAt=updated_at,
            description=self._description_from_facets(dataset_facets_payload),
            facets=dataset_facets_payload,
            deleted=False,
            columnLineage=None,
        )

    def get_runs_for_job(self, conn: Connection, namespace: str, name: str, limit: int, offset: int) -> RunsResponse:
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

    def get_dataset_versions(self, conn: Connection, namespace: str, name: str, limit: int, offset: int) -> DatasetVersionsResponse:
        dataset = self.get_dataset_by_name(conn, namespace, name)
        if not dataset:
            return DatasetVersionsResponse(versions=[], totalCount=0)
        dataset_row = conn.execute(
            select(assets.c.id).where(assets.c.namespace == namespace, assets.c.name == name)
        ).first()
        dataset_id = dataset_row[0]
        total_count = conn.execute(
            select(func.count()).select_from(asset_versions).where(asset_versions.c.asset_id == dataset_id)
        ).scalar_one()
        rows = conn.execute(
            select(asset_versions)
            .where(asset_versions.c.asset_id == dataset_id)
            .order_by(desc(asset_versions.c.created_at))
            .limit(limit)
            .offset(offset)
        ).mappings().all()
        versions = [
            self._dataset_version_model(conn, dataset, AssetVersionRow.from_mapping(row))
            for row in rows
        ]
        return DatasetVersionsResponse(versions=versions, totalCount=total_count)

    def get_facets_for_run(self, conn: Connection, run_public_id: str, facet_type: str) -> RunFacetsModel:
        run_row = conn.execute(select(runs).where(runs.c.run_id == run_public_id)).mappings().first()
        if not run_row:
            return RunFacetsModel(runId=run_public_id, facets={})
        typed_run = RunRow.from_mapping(run_row)
        if facet_type == 'job':
            facets_payload = self._collect_facets(conn, job_facets, 'job_id', typed_run.job_id)
        else:
            facets_payload = self._collect_facets(conn, run_facets, 'run_id', typed_run.id)
        return RunFacetsModel(runId=run_public_id, facets=facets_payload)

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

    def _dataset_version_model(
        self,
        conn: Connection,
        dataset: DatasetModel,
        version_row: AssetVersionRow,
    ) -> DatasetVersionModel:
        created_by_run = None
        if version_row.created_by_run_id:
            run_row = conn.execute(
                select(runs).where(runs.c.id == version_row.created_by_run_id)
            ).mappings().first()
            if run_row:
                created_by_run = self._run_model(conn, RunRow.from_mapping(run_row))
        return DatasetVersionModel(
            id=VersionedNamespaceName(
                namespace=dataset.namespace,
                name=dataset.name,
                version=version_row.version,
            ),
            type=dataset.type,
            assetKind=dataset.asset_kind,
            createdByRun=created_by_run,
            name=dataset.name,
            physicalName=dataset.physical_name,
            createdAt=version_row.created_at,
            version=version_row.version,
            storageUri=version_row.storage_uri,
            namespace=dataset.namespace,
            sourceName=dataset.source_name,
            fields=self._fields_from_snapshot(version_row.fields),
            tags=[],
            lastModifiedAt=version_row.created_at,
            description=dataset.description,
            lifecycleState=version_row.lifecycle_state or DatasetLifecycleState.ACTIVE.value,
            facets=version_row.facets or {},
        )

    def _job_runs(self, conn: Connection, job_id: str, limit: int, offset: int) -> list[RunModel]:
        rows = conn.execute(
            select(runs)
            .where(runs.c.job_id == job_id)
            .order_by(desc(func.coalesce(runs.c.ended_at, runs.c.started_at, runs.c.event_time, runs.c.created_at)))
            .limit(limit)
            .offset(offset)
        ).mappings().all()
        return [self._run_model(conn, RunRow.from_mapping(row)) for row in rows]

    def _run_model(self, conn: Connection, run_row: RunRow) -> RunModel:
        run_facets_payload = self._collect_facets(conn, run_facets, 'run_id', run_row.id)
        job_row = conn.execute(select(jobs).where(jobs.c.id == run_row.job_id)).mappings().first()
        job_version_name = JobVersionName(
            name=job_row['name'] if job_row else '',
            namespace=job_row['namespace'] if job_row else '',
            version='',
        )
        if run_row.job_version_id:
            version_row = conn.execute(
                select(job_versions.c.version_hash).where(job_versions.c.id == run_row.job_version_id)
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
        execution_parameters = run_facets_payload.get('execution_parameters', {})
        if isinstance(execution_parameters, dict):
            args = self._normalize_run_args(execution_parameters.get('parameters'))
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

    @staticmethod
    def _normalize_run_args(raw_args) -> dict[str, str]:
        if isinstance(raw_args, dict):
            return {
                str(key): '' if value is None else str(value)
                for key, value in raw_args.items()
            }

        if isinstance(raw_args, list):
            normalized: dict[str, str] = {}
            for item in raw_args:
                if not isinstance(item, dict):
                    continue
                key = item.get('key')
                if key is None:
                    continue
                normalized[str(key)] = '' if item.get('value') is None else str(item.get('value'))
            return normalized

        return {}

    def _current_job_datasets(self, conn: Connection, job_id: str) -> tuple[list[DatasetModel], list[DatasetModel]]:
        rows = conn.execute(
            select(assets, job_version_io_mapping.c.io_type)
            .select_from(
                job_versions.join(job_version_io_mapping, job_versions.c.id == job_version_io_mapping.c.job_version_id).join(
                    assets, assets.c.id == job_version_io_mapping.c.asset_id
                )
            )
            .where(job_versions.c.job_id == job_id, job_versions.c.is_current.is_(True))
        ).mappings().all()
        inputs = [
            self.get_dataset_by_id(conn, row['id'])
            for row in rows
            if row['io_type'] == JobVersionIOType.INPUT.value
        ]
        outputs = [
            self.get_dataset_by_id(conn, row['id'])
            for row in rows
            if row['io_type'] == JobVersionIOType.OUTPUT.value
        ]
        return [item for item in inputs if item is not None], [item for item in outputs if item is not None]

    def _latest_dataset_version(self, conn: Connection, dataset_id: str) -> AssetVersionRow | None:
        row = conn.execute(
            select(asset_versions)
            .where(asset_versions.c.asset_id == dataset_id)
            .order_by(desc(asset_versions.c.created_at))
            .limit(1)
        ).mappings().first()
        return AssetVersionRow.from_mapping(row) if row else None

    def _collect_facets(self, conn: Connection, table, owner_key: str, owner_id: str) -> dict:
        rows = conn.execute(
            select(table.c.facet_name, table.c.payload).where(getattr(table.c, owner_key) == owner_id)
        ).all()
        return {facet_name: payload for facet_name, payload in rows}

    @staticmethod
    def _job_type(facets_payload: dict) -> str:
        processing_type = facets_payload.get('jobType', {}).get('processingType')
        if processing_type in {item.value for item in JobProcessingType}:
            return processing_type
        return JobProcessingType.BATCH.value

    @staticmethod
    def _description_from_facets(facets_payload: dict) -> str:
        documentation = facets_payload.get('documentation', {})
        if isinstance(documentation, dict):
            description = documentation.get('description')
            if isinstance(description, str):
                return description
        return ''

    @staticmethod
    def _dataset_fields(
        facets_payload: dict,
        latest_version: AssetVersionRow | None,
    ) -> list[FieldModel]:
        if latest_version and latest_version.fields:
            return MetadataRepository._fields_from_snapshot(latest_version.fields)
        schema_facet = facets_payload.get('schema', {})
        return MetadataRepository._fields_from_snapshot(schema_facet.get('fields', []))

    @staticmethod
    def _fields_from_snapshot(fields: list[dict]) -> list[FieldModel]:
        return [
            FieldModel(
                name=field.get('name', ''),
                type=field.get('type'),
                tags=field.get('tags', []) or [],
                description=field.get('description', '') or '',
            )
            for field in fields or []
        ]

    @staticmethod
    def _web_run_state(run_state: str | None) -> WebRunState:
        if not run_state:
            return WebRunState.NEW

        try:
            normalized_state = RunEventType(run_state.upper())
        except ValueError:
            return WebRunState.NEW

        return RUN_EVENT_TO_WEB_RUN_STATE.get(normalized_state, WebRunState.NEW)
