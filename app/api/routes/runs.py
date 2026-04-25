from fastapi import APIRouter, Depends, HTTPException

from app.db.session import get_engine
from app.models.control_plane_api_models import RecipeRunCreateRequest, RunSubmissionCreateRequest
from app.services.run_service import RecipeRunService

router = APIRouter(prefix='/api/v1', tags=['runs'])


def get_run_service() -> RecipeRunService:
    return RecipeRunService(get_engine())


@router.post('/workspaces/{workspace_slug}/recipe-runs', status_code=201)
def create_recipe_run(
    workspace_slug: str,
    payload: RecipeRunCreateRequest,
    service: RecipeRunService = Depends(get_run_service),
) -> dict:
    try:
        return service.create_recipe_run(workspace_slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/workspaces/{workspace_slug}/recipe-runs')
def list_recipe_runs(workspace_slug: str, service: RecipeRunService = Depends(get_run_service)) -> dict:
    try:
        return service.list_recipe_runs(workspace_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/recipe-runs/{run_id}')
def get_recipe_run(run_id: str, service: RecipeRunService = Depends(get_run_service)) -> dict:
    recipe_run = service.get_recipe_run(run_id)
    if not recipe_run:
        raise HTTPException(status_code=404, detail='recipe run not found')
    return recipe_run


@router.post('/workspaces/{workspace_slug}/run-submissions', status_code=201)
def create_run_submission(
    workspace_slug: str,
    payload: RunSubmissionCreateRequest,
    service: RecipeRunService = Depends(get_run_service),
) -> dict:
    try:
        return service.create_run_submission(workspace_slug, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/workspaces/{workspace_slug}/run-submissions')
def list_run_submissions(workspace_slug: str, service: RecipeRunService = Depends(get_run_service)) -> dict:
    try:
        return service.list_run_submissions(workspace_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/run-submissions/{submission_id}')
def get_run_submission(submission_id: str, service: RecipeRunService = Depends(get_run_service)) -> dict:
    submission = service.get_run_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail='run submission not found')
    return submission
