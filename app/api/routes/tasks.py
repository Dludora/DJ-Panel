from fastapi import APIRouter, Depends

from app.api.dependencies import get_task_service
from app.api.errors import conflict, not_found
from app.models.api.control_plane import (
    TaskArtifactCreateRequest,
    TaskClaimRequest,
    TaskLogCreateRequest,
    TaskTransitionRequest,
)
from app.services.tasks import TaskService

router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.get("/workspaces/{workspace_slug}/tasks")
def list_tasks(
    workspace_slug: str, service: TaskService = Depends(get_task_service)
) -> dict:
    try:
        return service.list_tasks(workspace_slug)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/tasks/{task_id}")
def get_task(task_id: str, service: TaskService = Depends(get_task_service)) -> dict:
    task = service.get_task(task_id)
    if not task:
        raise not_found("task not found")
    return task


@router.post("/workspaces/{workspace_slug}/tasks/claim")
def claim_task(
    workspace_slug: str,
    payload: TaskClaimRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.claim_task(
            workspace_slug, payload.worker_id, payload.supported_task_kinds
        )
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: str,
    payload: TaskTransitionRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.start_task(task_id, payload)
    except ValueError as exc:
        raise conflict(str(exc)) from exc


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    payload: TaskTransitionRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.complete_task(task_id, payload)
    except ValueError as exc:
        raise conflict(str(exc)) from exc


@router.post("/tasks/{task_id}/fail")
def fail_task(
    task_id: str,
    payload: TaskTransitionRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.fail_task(task_id, payload)
    except ValueError as exc:
        raise conflict(str(exc)) from exc


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: str,
    payload: TaskTransitionRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.cancel_task(task_id, payload)
    except ValueError as exc:
        raise conflict(str(exc)) from exc


@router.post("/task-attempts/{attempt_id}/logs", status_code=201)
def create_task_log(
    attempt_id: str,
    payload: TaskLogCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.create_log(attempt_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/task-attempts/{attempt_id}/logs")
def list_task_logs(
    attempt_id: str, service: TaskService = Depends(get_task_service)
) -> dict:
    return service.list_logs(attempt_id)


@router.post("/task-attempts/{attempt_id}/artifacts", status_code=201)
def create_task_artifact(
    attempt_id: str,
    payload: TaskArtifactCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> dict:
    try:
        return service.create_artifact(attempt_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/task-attempts/{attempt_id}/artifacts")
def list_task_artifacts(
    attempt_id: str, service: TaskService = Depends(get_task_service)
) -> dict:
    return service.list_artifacts(attempt_id)
