from __future__ import annotations

from sqlalchemy.engine import Engine

from dj_panel.app.models.api import AssetCreateRequest, AssetRenameRequest, AssetVersionCreateRequest
from dj_panel.app.models.constant import AssetCatalogSource, AssetKind
from dj_panel.app.repositories.assets_repo import AssetRepository


class AssetService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.repo = AssetRepository()

    def list_tags(self) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_tags(conn).to_api_dict()

    def upsert_tag(self, name: str, description: str) -> dict:
        with self.engine.begin() as conn:
            return self.repo.upsert_tag(conn, name, description).to_api_dict()

    def list_assets(
        self,
        namespace: str | None,
        asset_kind: AssetKind | None,
        limit: int,
        offset: int,
    ) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_assets(
                conn, namespace, asset_kind, limit, offset
            ).to_api_dict()

    def list_datasets(
        self,
        namespace: str,
        limit: int,
        offset: int,
        asset_kind: AssetKind | None = None,
    ) -> dict:
        payload = self.list_assets(namespace, asset_kind, limit, offset)
        return {
            "datasets": payload["assets"],
            "totalCount": payload["totalCount"],
        }

    def get_asset(
        self, namespace: str, name: str, asset_kind: AssetKind | None = None
    ) -> dict | None:
        with self.engine.begin() as conn:
            asset = self.repo.get_asset_by_name(conn, namespace, name, asset_kind)
            return asset.to_api_dict() if asset else None

    def get_asset_by_id(self, asset_id: str) -> dict | None:
        with self.engine.begin() as conn:
            asset = self.repo.get_asset_by_id(conn, asset_id)
            return asset.to_api_dict() if asset else None

    def get_asset_versions(
        self,
        namespace: str,
        name: str,
        limit: int,
        offset: int,
        asset_kind: AssetKind | None = None,
    ) -> dict:
        with self.engine.begin() as conn:
            return self.repo.get_asset_versions(
                conn, namespace, name, limit, offset, asset_kind
            ).to_api_dict()

    def register_asset(self, payload: AssetCreateRequest) -> dict:
        with self.engine.begin() as conn:
            asset = self.repo.upsert_asset(
                conn,
                namespace=payload.namespace,
                name=payload.name,
                asset_kind=payload.asset_kind,
                description=payload.description,
                facets=payload.facets,
                catalog_source=AssetCatalogSource.USER_REGISTERED,
            )
            return self.repo.get_asset_by_id(conn, asset.id).to_api_dict()

    def register_asset_version(
        self, asset_id: str, payload: AssetVersionCreateRequest
    ) -> dict:
        with self.engine.begin() as conn:
            asset = self.repo.get_asset_by_id(conn, asset_id)
            if not asset:
                raise ValueError("asset not found")
            self.repo.create_asset_version(
                conn,
                asset_id=asset_id,
                version=payload.version,
                storage_uri=payload.storage_uri,
                fields=payload.fields,
                facets=payload.facets,
                lifecycle_state=payload.lifecycle_state,
            )
            versions = self.repo.get_asset_versions(
                conn, asset.namespace, asset.name, limit=1, offset=0
            )
            return versions.versions[0].to_api_dict() if versions.versions else {}

    def rename_asset(self, asset_id: str, payload: AssetRenameRequest) -> dict:
        with self.engine.begin() as conn:
            asset = self.repo.rename_asset(conn, asset_id, payload.name)
            if not asset:
                raise ValueError("asset not found")
            return asset.to_api_dict()
