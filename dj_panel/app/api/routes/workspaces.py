from fastapi import APIRouter, Depends

from dj_panel.app.api.dependencies import get_workspace_service
from dj_panel.app.api.errors import not_found
from dj_panel.app.models.api import WorkspaceCreateRequest, WorkspaceMemberAddRequest
from dj_panel.app.services.workspaces_service import WorkspaceService

router = APIRouter(prefix='/api/v1', tags=['workspaces'])


@router.post('/workspaces', status_code=201)
def create_workspace(
    payload: WorkspaceCreateRequest,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.create_workspace(payload.slug, payload.name, payload.description, payload.owner_name)


@router.get('/workspaces')
def list_workspaces(service: WorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.list_workspaces()


@router.post('/workspaces/{workspace_slug}/members', status_code=201)
def add_workspace_member(
    workspace_slug: str,
    payload: WorkspaceMemberAddRequest,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    try:
        return service.add_member(workspace_slug, payload.user_name, payload.role)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get('/workspaces/{workspace_slug}/members')
def list_workspace_members(
    workspace_slug: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    try:
        return service.list_members(workspace_slug)
    except ValueError as exc:
        raise not_found(str(exc)) from exc
