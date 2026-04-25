from fastapi import APIRouter, Depends, HTTPException

from app.db.session import get_engine
from app.models.control_plane_api_models import WorkerHeartbeatRequest, WorkerRegisterRequest
from app.services.worker_service import WorkerService

router = APIRouter(prefix='/api/v1', tags=['workers'])


def get_worker_service() -> WorkerService:
    return WorkerService(get_engine())


@router.post('/workspaces/{workspace_slug}/workers/register', status_code=201)
def register_worker(
    workspace_slug: str,
    payload: WorkerRegisterRequest,
    service: WorkerService = Depends(get_worker_service),
) -> dict:
    try:
        return service.register_worker(workspace_slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/workers/{worker_id}/heartbeat')
def worker_heartbeat(
    worker_id: str,
    payload: WorkerHeartbeatRequest,
    service: WorkerService = Depends(get_worker_service),
) -> dict:
    try:
        return service.heartbeat(worker_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/workspaces/{workspace_slug}/workers')
def list_workers(workspace_slug: str, service: WorkerService = Depends(get_worker_service)) -> dict:
    try:
        return service.list_workers(workspace_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
