from fastapi import APIRouter, Depends

from dj_panel.app.api.dependencies import get_worker_service
from dj_panel.app.api.errors import not_found
from dj_panel.app.models.api import (
    WorkerHeartbeatRequest,
    WorkerRegisterRequest,
)
from dj_panel.app.services.workers_service import WorkerService

router = APIRouter(prefix="/api/v1", tags=["workers"])


@router.post("/workspaces/{workspace_slug}/workers/register", status_code=201)
def register_worker(
    workspace_slug: str,
    payload: WorkerRegisterRequest,
    service: WorkerService = Depends(get_worker_service),
) -> dict:
    try:
        return service.register_worker(workspace_slug, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.post("/workers/{worker_id}/heartbeat")
def worker_heartbeat(
    worker_id: str,
    payload: WorkerHeartbeatRequest,
    service: WorkerService = Depends(get_worker_service),
) -> dict:
    try:
        return service.heartbeat(worker_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/workspaces/{workspace_slug}/workers")
def list_workers(
    workspace_slug: str, service: WorkerService = Depends(get_worker_service)
) -> dict:
    try:
        return service.list_workers(workspace_slug)
    except ValueError as exc:
        raise not_found(str(exc)) from exc
