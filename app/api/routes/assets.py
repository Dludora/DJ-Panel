from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.api.dependencies import get_asset_service
from app.api.errors import not_found
from app.models.api import AssetCreateRequest, AssetRenameRequest, AssetVersionCreateRequest
from app.models.constant import AssetKind
from app.services.assets import AssetService

router = APIRouter(prefix="/api/v1", tags=["assets"])


class UpsertTagRequest(BaseModel):
    description: str = ""


@router.get("/tags")
def list_tags(service: AssetService = Depends(get_asset_service)) -> dict:
    return service.list_tags()


@router.put("/tags/{tag_name}")
def upsert_tag(
    tag_name: str,
    request: UpsertTagRequest,
    service: AssetService = Depends(get_asset_service),
) -> dict:
    return service.upsert_tag(tag_name, request.description)


@router.get("/assets")
def list_assets(
    namespace: str | None = Query(default=None),
    assetKind: AssetKind | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AssetService = Depends(get_asset_service),
):
    return service.list_assets(namespace, assetKind, limit, offset)


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def register_asset(
    payload: AssetCreateRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.register_asset(payload)


@router.get("/assets/{asset_id}")
def get_asset_by_id(
    asset_id: str,
    service: AssetService = Depends(get_asset_service),
):
    asset = service.get_asset_by_id(asset_id)
    if not asset:
        raise not_found("asset not found")
    return asset


@router.patch("/assets/{asset_id}")
def rename_asset(
    asset_id: str,
    payload: AssetRenameRequest,
    service: AssetService = Depends(get_asset_service),
):
    try:
        return service.rename_asset(asset_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.post("/assets/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
def register_asset_version(
    asset_id: str,
    payload: AssetVersionCreateRequest,
    service: AssetService = Depends(get_asset_service),
):
    try:
        result = service.register_asset_version(asset_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc
    return result


@router.get("/namespaces/{namespace:path}/datasets")
def list_datasets(
    namespace: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AssetService = Depends(get_asset_service),
):
    return service.list_datasets(namespace, limit, offset, AssetKind.DATASET)


@router.get("/namespaces/{namespace:path}/assets/{asset_name:path}/versions")
def get_asset_versions(
    namespace: str,
    asset_name: str,
    assetKind: AssetKind | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AssetService = Depends(get_asset_service),
):
    return service.get_asset_versions(namespace, asset_name, limit, offset, assetKind)


@router.get("/namespaces/{namespace:path}/assets/{asset_name:path}")
def get_asset(
    namespace: str,
    asset_name: str,
    assetKind: AssetKind | None = Query(default=None),
    service: AssetService = Depends(get_asset_service),
):
    asset = service.get_asset(namespace, asset_name, assetKind)
    if not asset:
        raise not_found("asset not found")
    return asset


@router.get("/namespaces/{namespace:path}/datasets/{dataset_name:path}/versions")
def get_dataset_versions(
    namespace: str,
    dataset_name: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AssetService = Depends(get_asset_service),
):
    return service.get_asset_versions(
        namespace, dataset_name, limit, offset, AssetKind.DATASET
    )


@router.get("/namespaces/{namespace:path}/datasets/{dataset_name:path}")
def get_dataset(
    namespace: str,
    dataset_name: str,
    service: AssetService = Depends(get_asset_service),
):
    asset = service.get_asset(namespace, dataset_name, AssetKind.DATASET)
    if not asset:
        raise not_found("dataset not found")
    return asset
