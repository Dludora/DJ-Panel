from fastapi import APIRouter, Depends, status

from dj_panel.app.api.dependencies import get_run_submission_service
from dj_panel.app.api.errors import conflict, not_found
from dj_panel.app.models.api import RunSubmissionCreateRequest
from dj_panel.app.services.run_submissions import RunSubmissionService

router = APIRouter(prefix="/api/v1", tags=["run-submissions"])


@router.post(
    "/workspaces/{workspace_slug}/run-submissions", status_code=status.HTTP_201_CREATED
)
def create_run_submission(
    workspace_slug: str,
    payload: RunSubmissionCreateRequest,
    service: RunSubmissionService = Depends(get_run_submission_service),
) -> dict:
    try:
        return service.create_run_submission(workspace_slug, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/workspaces/{workspace_slug}/run-submissions")
def list_run_submissions(
    workspace_slug: str, service: RunSubmissionService = Depends(get_run_submission_service)
) -> dict:
    try:
        return service.list_run_submissions(workspace_slug)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/run-submissions/{submission_id}")
def get_run_submission(
    submission_id: str, service: RunSubmissionService = Depends(get_run_submission_service)
) -> dict:
    submission = service.get_run_submission(submission_id)
    if not submission:
        raise not_found("run submission not found")
    return submission


@router.post("/run-submissions/{submission_id}/resume")
def resume_run_submission(
    submission_id: str, service: RunSubmissionService = Depends(get_run_submission_service)
) -> dict:
    try:
        return service.resume_run_submission(submission_id)
    except ValueError as exc:
        raise not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise conflict(str(exc)) from exc


@router.post("/run-submissions/{submission_id}/cancel")
def cancel_run_submission(
    submission_id: str, service: RunSubmissionService = Depends(get_run_submission_service)
) -> dict:
    try:
        return service.cancel_run_submission(submission_id)
    except ValueError as exc:
        raise not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise conflict(str(exc)) from exc
