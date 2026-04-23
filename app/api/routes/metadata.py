from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_engine
from app.services.metadata import MetadataService

router = APIRouter(prefix='/api/v1', tags=['metadata'])


class UpsertTagRequest(BaseModel):
    description: str = ''


def get_metadata_service() -> MetadataService:
    return MetadataService(get_engine())


@router.get('/namespaces')
def list_namespaces(service: MetadataService = Depends(get_metadata_service)) -> dict:
    return service.list_namespaces()


@router.get('/tags')
def list_tags(service: MetadataService = Depends(get_metadata_service)) -> dict:
    return service.list_tags()


@router.put('/tags/{tag_name}')
def upsert_tag(
    tag_name: str,
    request: UpsertTagRequest,
    service: MetadataService = Depends(get_metadata_service),
) -> dict:
    return service.upsert_tag(tag_name, request.description)


@router.get('/jobs')
def list_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    lastRunStates: str | None = Query(default=None),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.list_jobs(None, limit, offset, lastRunStates)


@router.get('/namespaces/{namespace:path}/jobs')
def list_jobs_by_namespace(
    namespace: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    lastRunStates: str | None = Query(default=None),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.list_jobs(namespace, limit, offset, lastRunStates)


@router.get('/namespaces/{namespace:path}/jobs/{job_name:path}/runs')
def get_runs(
    namespace: str,
    job_name: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.get_runs(namespace, job_name, limit, offset)


@router.get('/namespaces/{namespace:path}/jobs/{job_name:path}')
def get_job(namespace: str, job_name: str, service: MetadataService = Depends(get_metadata_service)):
    job = service.get_job(namespace, job_name)
    if not job:
        raise HTTPException(status_code=404, detail='job not found')
    return job


@router.get('/namespaces/{namespace:path}/datasets')
def list_datasets(
    namespace: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.list_datasets(namespace, limit, offset)


@router.get('/namespaces/{namespace:path}/datasets/{dataset_name:path}/versions')
def get_dataset_versions(
    namespace: str,
    dataset_name: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.get_dataset_versions(namespace, dataset_name, limit, offset)


@router.get('/namespaces/{namespace:path}/datasets/{dataset_name:path}')
def get_dataset(namespace: str, dataset_name: str, service: MetadataService = Depends(get_metadata_service)):
    dataset = service.get_dataset(namespace, dataset_name)
    if not dataset:
        raise HTTPException(status_code=404, detail='dataset not found')
    return dataset


@router.get('/jobs/runs/{run_id}/facets')
def get_run_or_job_facets(
    run_id: str,
    type: str = Query(default='run', pattern='^(run|job)$'),
    service: MetadataService = Depends(get_metadata_service),
):
    return service.get_run_or_job_facets(run_id, type)
