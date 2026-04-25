from fastapi import APIRouter, Depends

from app.db.session import get_engine
from app.models.control_plane_api_models import WorkspaceCreateRequest
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix='/api/v1', tags=['workspaces'])


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(get_engine())


@router.post('/workspaces', status_code=201)
def create_workspace(
    payload: WorkspaceCreateRequest,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.create_workspace(payload.slug, payload.name, payload.description)


@router.get('/workspaces')
def list_workspaces(service: WorkspaceService = Depends(get_workspace_service)) -> dict:
    return service.list_workspaces()
