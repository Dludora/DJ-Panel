from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import ValidationError

from dj_panel.app.api.dependencies import get_lineage_service
from dj_panel.app.api.errors import bad_request, not_found, validation_error
from dj_panel.app.models.api import IngestionResponse
from dj_panel.app.utils.openlineage_utils import parse_event
from dj_panel.app.services.lineage_service import LineageService

router = APIRouter(prefix="/api/v1", tags=["lineage"])


@router.post("/lineage", status_code=status.HTTP_201_CREATED)
async def create_lineage_event(
    request: Request,
    service: LineageService = Depends(get_lineage_service),
) -> IngestionResponse:
    payload = await request.json()
    try:
        event = parse_event(payload)
    except ValidationError as exc:
        raise validation_error(exc.errors()) from exc
    result = service.ingest(event, payload)
    return IngestionResponse(projected=result.projected)


@router.get("/lineage")
def get_lineage(
    nodeId: str = Query(...),
    depth: int = Query(default=1, ge=0, le=20),
    service: LineageService = Depends(get_lineage_service),
):
    try:
        return service.get_lineage(node_id=nodeId, depth=depth)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


@router.get("/events/lineage")
def list_lineage_events(
    limit: int = Query(default=50, ge=1, le=200),
    service: LineageService = Depends(get_lineage_service),
) -> dict:
    return service.list_lineage_events(limit)


@router.get("/namespaces")
def list_namespaces(service: LineageService = Depends(get_lineage_service)) -> dict:
    return service.list_namespaces()


@router.get("/jobs")
def list_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    lastRunStates: str | None = Query(default=None),
    service: LineageService = Depends(get_lineage_service),
):
    return service.list_jobs(None, limit, offset, lastRunStates)


@router.get("/namespaces/{namespace:path}/jobs")
def list_jobs_by_namespace(
    namespace: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    lastRunStates: str | None = Query(default=None),
    service: LineageService = Depends(get_lineage_service),
):
    return service.list_jobs(namespace, limit, offset, lastRunStates)


@router.get("/namespaces/{namespace:path}/jobs/{job_name:path}/runs")
def get_runs(
    namespace: str,
    job_name: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: LineageService = Depends(get_lineage_service),
):
    return service.get_runs(namespace, job_name, limit, offset)


@router.get("/namespaces/{namespace:path}/jobs/{job_name:path}")
def get_job(
    namespace: str,
    job_name: str,
    service: LineageService = Depends(get_lineage_service),
):
    job = service.get_job(namespace, job_name)
    if not job:
        raise not_found("job not found")
    return job


@router.get("/jobs/runs/{run_id}/facets")
def get_run_or_job_facets(
    run_id: str,
    type: str = Query(default="run", pattern="^(run|job)$"),
    service: LineageService = Depends(get_lineage_service),
):
    return service.get_run_or_job_facets(run_id, type)
