from __future__ import annotations

import hashlib
import json

from sqlalchemy import desc, func, insert, select, update
from sqlalchemy.engine import Connection

from dj_panel.app.db.schema import (
    asset_facets,
    asset_versions,
    assets,
    jobs,
    job_versions,
    run_facets,
    runs,
)
from dj_panel.app.db.rows import AssetRow, AssetVersionRow, RunRow
from dj_panel.app.models.api import (
    AssetModel,
    AssetVersionModel,
    AssetVersionsResponse,
    AssetsResponse,
    DatasetModel,
    DatasetVersionModel,
    FieldModel,
    JobVersionName,
    NamespaceName,
    RunModel,
    TagModel,
    TagsResponse,
    VersionedNamespaceName,
)
from dj_panel.app.models.constant import (
    AssetCatalogSource,
    AssetKind,
    DatasetLifecycleState,
    RUN_EVENT_TO_WEB_RUN_STATE,
    WebRunState,
)
from dj_panel.app.models.protocols.openlineage import RunEventType
from dj_panel.app.utils.common_utils import new_id, utc_now


class AssetRepository:
    def get_current_asset_version_row(
        self, conn: Connection, asset_id: str
    ) -> AssetVersionRow | None:
        asset_row = (
            conn.execute(
                select(assets.c.current_version_id).where(assets.c.id == asset_id)
            )
            .mappings()
            .first()
        )
        if not asset_row or not asset_row["current_version_id"]:
            return None
        row = (
            conn.execute(
                select(asset_versions).where(
                    asset_versions.c.id == asset_row["current_version_id"]
                )
            )
            .mappings()
            .first()
        )
        return AssetVersionRow.from_mapping(row) if row else None

    def set_current_asset_version(
        self, conn: Connection, asset_id: str, version_id: str
    ) -> None:
        conn.execute(
            update(assets)
            .where(assets.c.id == asset_id)
            .values(current_version_id=version_id, updated_at=utc_now())
        )

    def upsert_asset_facets(
        self,
        conn: Connection,
        asset_id: str,
        facets: dict,
        *,
        asset_version_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._upsert_asset_facets(
            conn, asset_id, facets, asset_version_id, run_id
        )

    def attach_asset_facets_to_asset_version(
        self, conn: Connection, run_db_id: str, asset_id: str, asset_version_id: str
    ) -> None:
        conn.execute(
            update(asset_facets)
            .where(
                asset_facets.c.run_id == run_db_id,
                asset_facets.c.asset_id == asset_id,
            )
            .values(asset_version_id=asset_version_id, updated_at=utc_now())
        )

    def list_tags(self, conn: Connection) -> TagsResponse:
        return TagsResponse(tags=[])

    def upsert_tag(self, conn: Connection, name: str, description: str) -> TagModel:
        return TagModel(name=name, description=description)

    def list_assets(
        self,
        conn: Connection,
        namespace: str | None,
        asset_kind: AssetKind | None,
        limit: int,
        offset: int,
    ) -> AssetsResponse:
        base_query = select(assets.c.id)
        count_query = select(func.count()).select_from(assets)
        if namespace:
            base_query = base_query.where(assets.c.namespace == namespace)
            count_query = count_query.where(assets.c.namespace == namespace)
        if asset_kind:
            base_query = base_query.where(assets.c.asset_kind == asset_kind.value)
            count_query = count_query.where(assets.c.asset_kind == asset_kind.value)
        total_count = conn.execute(count_query).scalar_one()
        asset_ids = [
            row[0]
            for row in conn.execute(
                base_query.order_by(assets.c.updated_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        ]
        items = [self.get_asset_by_id(conn, asset_id) for asset_id in asset_ids]
        return AssetsResponse(
            assets=[item for item in items if item is not None],
            totalCount=total_count,
        )

    def get_asset_by_name(
        self,
        conn: Connection,
        namespace: str,
        name: str,
        asset_kind: AssetKind | None = None,
    ) -> AssetModel | None:
        query = select(assets).where(
            assets.c.namespace == namespace, assets.c.name == name
        )
        if asset_kind:
            query = query.where(assets.c.asset_kind == asset_kind.value)
        row = conn.execute(query).mappings().first()
        return self.get_asset_by_id(conn, row["id"]) if row else None

    def get_asset_by_id(self, conn: Connection, asset_id: str) -> AssetModel | None:
        row = (
            conn.execute(select(assets).where(assets.c.id == asset_id))
            .mappings()
            .first()
        )
        if not row:
            return None
        asset_row = AssetRow.from_mapping(row)
        facets_payload = self._collect_current_asset_facets(conn, asset_row)
        current_version = self._current_or_latest_asset_version(conn, asset_row)
        fields = self._asset_fields(facets_payload, current_version)
        updated_at = (
            current_version.created_at if current_version else asset_row.updated_at
        )
        return DatasetModel(
            catalogId=asset_row.id,
            id=NamespaceName(namespace=asset_row.namespace, name=asset_row.name),
            type="DB_TABLE",
            assetKind=asset_row.asset_kind,
            catalogSource=asset_row.catalog_source,
            name=asset_row.name,
            physicalName=f"{asset_row.namespace}.{asset_row.name}",
            createdAt=asset_row.created_at,
            updatedAt=updated_at,
            namespace=asset_row.namespace,
            sourceName="default",
            fields=fields,
            tags=[],
            lastModifiedAt=updated_at,
            description=self._description_from_facets(facets_payload),
            facets=facets_payload,
            deleted=False,
            columnLineage=None,
        )

    def rename_asset(self, conn: Connection, asset_id: str, name: str) -> AssetModel | None:
        row = (
            conn.execute(select(assets).where(assets.c.id == asset_id))
            .mappings()
            .first()
        )
        if not row:
            return None
        conn.execute(
            update(assets)
            .where(assets.c.id == asset_id)
            .values(name=name, updated_at=utc_now())
        )
        return self.get_asset_by_id(conn, asset_id)

    def get_asset_versions(
        self,
        conn: Connection,
        namespace: str,
        name: str,
        limit: int,
        offset: int,
        asset_kind: AssetKind | None = None,
    ) -> AssetVersionsResponse:
        asset = self.get_asset_by_name(conn, namespace, name, asset_kind)
        if not asset:
            return AssetVersionsResponse(versions=[], totalCount=0)
        query = select(assets.c.id).where(
            assets.c.namespace == namespace, assets.c.name == name
        )
        if asset_kind:
            query = query.where(assets.c.asset_kind == asset_kind.value)
        asset_row = conn.execute(query).first()
        asset_id = asset_row[0]
        total_count = conn.execute(
            select(func.count())
            .select_from(asset_versions)
            .where(asset_versions.c.asset_id == asset_id)
        ).scalar_one()
        rows = (
            conn.execute(
                select(asset_versions)
                .where(asset_versions.c.asset_id == asset_id)
                .order_by(desc(asset_versions.c.created_at))
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        versions = [
            self._asset_version_model(conn, asset, AssetVersionRow.from_mapping(row))
            for row in rows
        ]
        return AssetVersionsResponse(versions=versions, totalCount=total_count)

    def upsert_asset(
        self,
        conn: Connection,
        namespace: str,
        name: str,
        asset_kind: str,
        description: str,
        facets: dict,
        catalog_source: AssetCatalogSource = AssetCatalogSource.USER_REGISTERED,
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
            current = AssetRow.from_mapping(existing)
            next_kind = (
                asset_kind
                if current.asset_kind == "DATASET" and asset_kind != "DATASET"
                else current.asset_kind
            )
            values = {
                "asset_kind": next_kind,
                "catalog_source": (
                    current.catalog_source
                    if current.catalog_source
                    == AssetCatalogSource.USER_REGISTERED.value
                    else catalog_source.value
                ),
                "updated_at": now,
            }
            conn.execute(
                update(assets).where(assets.c.id == current.id).values(**values)
            )
            asset_id = current.id
            asset_row = AssetRow.from_mapping({**dict(existing), **values})
        else:
            asset_id = new_id()
            values = {
                "id": asset_id,
                "namespace": namespace,
                "name": name,
                "asset_kind": asset_kind,
                "catalog_source": catalog_source.value,
                "current_version_id": None,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(insert(assets).values(**values))
            asset_row = AssetRow.from_mapping(values)

        if description:
            facets = {
                **facets,
                "documentation": {
                    **(
                        facets.get("documentation", {})
                        if isinstance(facets.get("documentation"), dict)
                        else {}
                    ),
                    "description": description,
                },
            }
        self._upsert_asset_facets(conn, asset_id, facets, None, None)
        return asset_row

    def create_asset_version(
        self,
        conn: Connection,
        asset_id: str,
        version: str,
        storage_uri: str | None,
        fields: list[dict],
        facets: dict,
        lifecycle_state: str,
    ) -> AssetVersionRow:
        existing = (
            conn.execute(
                select(asset_versions).where(
                    asset_versions.c.asset_id == asset_id,
                    asset_versions.c.version == version,
                )
            )
            .mappings()
            .first()
        )
        now = utc_now()
        values = {
            "asset_id": asset_id,
            "version": version,
            "storage_uri": storage_uri,
            "fields": fields,
            "facets": facets,
            "lifecycle_state": lifecycle_state,
            "created_at": now,
        }
        if existing:
            conn.execute(
                update(asset_versions)
                .where(asset_versions.c.id == existing["id"])
                .values(**values)
            )
            version_row = AssetVersionRow.from_mapping({**dict(existing), **values})
            self.set_current_asset_version(conn, asset_id, version_row.id)
            return version_row

        row = {"id": new_id(), "created_by_run_id": None, **values}
        conn.execute(insert(asset_versions).values(**row))
        version_row = AssetVersionRow.from_mapping(row)
        self.set_current_asset_version(conn, asset_id, version_row.id)
        return version_row

    def compute_asset_version(
        self,
        asset: AssetRow,
        payloads: dict,
        *,
        event_scope: str,
        run_public_id: str | None = None,
    ) -> str:
        snapshot = {
            "asset_namespace": asset.namespace,
            "asset_name": asset.name,
            "event_scope": event_scope,
            "run_id": run_public_id,
            "payloads": payloads,
        }
        return hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def extract_storage_uri_from_facets(self, payloads: dict) -> str | None:
        candidates = [
            payloads.get("dataSource", {}).get("uri"),
            payloads.get("datasource", {}).get("uri"),
            payloads.get("mlflow_model", {}).get("model_uri"),
            payloads.get("mlflow_model", {}).get("artifact_uri"),
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate)
        return None

    def upsert_asset_version(
        self,
        conn: Connection,
        asset: AssetRow,
        payloads: dict,
        *,
        event_scope: str,
        run: RunRow | None = None,
        created_by_run_id: str | None = None,
        set_current: bool = False,
    ) -> AssetVersionRow:
        version = self.compute_asset_version(
            asset,
            payloads,
            event_scope=event_scope,
            run_public_id=run.run_id if run else None,
        )
        existing = (
            conn.execute(
                select(asset_versions).where(
                    asset_versions.c.asset_id == asset.id,
                    asset_versions.c.version == version,
                )
            )
            .mappings()
            .first()
        )
        now = utc_now()
        values = {
            "asset_id": asset.id,
            "version": version,
            "created_by_run_id": created_by_run_id,
            "storage_uri": self.extract_storage_uri_from_facets(payloads),
            "fields": payloads.get("schema", {}).get("fields", []),
            "facets": payloads,
            "lifecycle_state": (
                payloads.get("lifecycleStateChange", {}).get("lifecycleStateChange")
                or DatasetLifecycleState.ACTIVE.value
            ),
            "created_at": now,
        }
        if existing:
            conn.execute(
                update(asset_versions)
                .where(asset_versions.c.id == existing["id"])
                .values(**values)
            )
            version_row = AssetVersionRow.from_mapping({**dict(existing), **values})
        else:
            row = {"id": new_id(), **values}
            conn.execute(insert(asset_versions).values(**row))
            version_row = AssetVersionRow.from_mapping(row)

        if set_current:
            self.set_current_asset_version(conn, asset.id, version_row.id)
        return version_row

    def resolve_input_version_from_lineage(
        self,
        conn: Connection,
        asset: AssetRow,
        payloads: dict,
        *,
        run: RunRow | None = None,
        event_scope: str,
    ) -> AssetVersionRow:
        current = self.get_current_asset_version_row(conn, asset.id)
        if current:
            return current

        return self.upsert_asset_version(
            conn,
            asset,
            payloads,
            event_scope=event_scope,
            run=run,
            created_by_run_id=None,
            set_current=True,
        )

    def _asset_version_model(
        self,
        conn: Connection,
        asset: DatasetModel,
        version_row: AssetVersionRow,
    ) -> AssetVersionModel:
        created_by_run = None
        if version_row.created_by_run_id:
            run_row = (
                conn.execute(
                    select(runs).where(runs.c.id == version_row.created_by_run_id)
                )
                .mappings()
                .first()
            )
            if run_row:
                created_by_run = self._run_model(conn, RunRow.from_mapping(run_row))
        return DatasetVersionModel(
            id=VersionedNamespaceName(
                namespace=asset.namespace,
                name=asset.name,
                version=version_row.version,
            ),
            type=asset.type,
            assetKind=asset.asset_kind,
            createdByRun=created_by_run,
            name=asset.name,
            physicalName=asset.physical_name,
            createdAt=version_row.created_at,
            version=version_row.version,
            storageUri=version_row.storage_uri,
            namespace=asset.namespace,
            sourceName=asset.source_name,
            fields=self._fields_from_snapshot(version_row.fields),
            tags=[],
            lastModifiedAt=version_row.created_at,
            description=asset.description,
            lifecycleState=version_row.lifecycle_state
            or DatasetLifecycleState.ACTIVE.value,
            facets=version_row.facets or {},
        )

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
        args = {}
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

    def _latest_asset_version(
        self, conn: Connection, asset_id: str
    ) -> AssetVersionRow | None:
        row = (
            conn.execute(
                select(asset_versions)
                .where(asset_versions.c.asset_id == asset_id)
                .order_by(desc(asset_versions.c.created_at))
                .limit(1)
            )
            .mappings()
            .first()
        )
        return AssetVersionRow.from_mapping(row) if row else None

    def _current_or_latest_asset_version(
        self, conn: Connection, asset_row: AssetRow
    ) -> AssetVersionRow | None:
        if asset_row.current_version_id:
            row = (
                conn.execute(
                    select(asset_versions).where(
                        asset_versions.c.id == asset_row.current_version_id
                    )
                )
                .mappings()
                .first()
            )
            if row:
                return AssetVersionRow.from_mapping(row)
        return self._latest_asset_version(conn, asset_row.id)

    def _collect_current_asset_facets(
        self, conn: Connection, asset_row: AssetRow
    ) -> dict:
        base_rows = conn.execute(
            select(asset_facets.c.facet_name, asset_facets.c.payload).where(
                asset_facets.c.asset_id == asset_row.id,
                asset_facets.c.asset_version_id.is_(None),
                asset_facets.c.run_id.is_(None),
            )
        ).all()
        base_facets = {facet_name: payload for facet_name, payload in base_rows}

        if asset_row.current_version_id:
            rows = conn.execute(
                select(asset_facets.c.facet_name, asset_facets.c.payload).where(
                    asset_facets.c.asset_version_id == asset_row.current_version_id
                )
            ).all()
            if rows:
                version_facets = {facet_name: payload for facet_name, payload in rows}
                return {**base_facets, **version_facets}

        if base_facets:
            return base_facets

        current_version = self._current_or_latest_asset_version(conn, asset_row)
        if current_version and current_version.facets:
            return {**base_facets, **current_version.facets}
        return {}

    def _upsert_asset_facets(
        self,
        conn: Connection,
        asset_id: str,
        facets: dict,
        asset_version_id: str | None,
        run_id: str | None,
    ) -> None:
        now = utc_now()
        for facet_name, payload in facets.items():
            query = select(asset_facets).where(
                asset_facets.c.asset_id == asset_id,
                asset_facets.c.facet_name == facet_name,
            )
            if run_id is None:
                query = query.where(asset_facets.c.run_id.is_(None))
            else:
                query = query.where(asset_facets.c.run_id == run_id)

            if asset_version_id is None:
                query = query.where(asset_facets.c.asset_version_id.is_(None))
            else:
                query = query.where(asset_facets.c.asset_version_id == asset_version_id)

            existing = conn.execute(query).mappings().first()
            values = {
                "payload": payload,
                "updated_at": now,
                "asset_version_id": asset_version_id,
                "run_id": run_id,
            }
            if existing:
                conn.execute(
                    update(asset_facets)
                    .where(asset_facets.c.id == existing["id"])
                    .values(**values)
                )
            else:
                conn.execute(
                    insert(asset_facets).values(
                        id=new_id(),
                        asset_id=asset_id,
                        facet_name=facet_name,
                        **values,
                    )
                )

    @staticmethod
    def _collect_facets(conn: Connection, table, owner_key: str, owner_id: str) -> dict:
        rows = conn.execute(
            select(table.c.facet_name, table.c.payload).where(
                getattr(table.c, owner_key) == owner_id
            )
        ).all()
        return {facet_name: payload for facet_name, payload in rows}

    @staticmethod
    def _description_from_facets(facets_payload: dict) -> str:
        documentation = facets_payload.get("documentation", {})
        if isinstance(documentation, dict):
            description = documentation.get("description")
            if isinstance(description, str):
                return description
        return ""

    @staticmethod
    def _asset_fields(
        facets_payload: dict,
        latest_version: AssetVersionRow | None,
    ) -> list[FieldModel]:
        if latest_version and latest_version.fields:
            return AssetRepository._fields_from_snapshot(latest_version.fields)
        schema_facet = facets_payload.get("schema", {})
        return AssetRepository._fields_from_snapshot(schema_facet.get("fields", []))

    @staticmethod
    def _fields_from_snapshot(fields: list[dict]) -> list[FieldModel]:
        return [
            FieldModel(
                name=field.get("name", ""),
                type=field.get("type"),
                tags=field.get("tags", []) or [],
                description=field.get("description", "") or "",
            )
            for field in fields or []
        ]

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
