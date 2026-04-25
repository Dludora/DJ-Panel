from __future__ import annotations

from sqlalchemy.engine import Engine
from typing import Optional

from app.models.control_plane_api_models import (
    RecipeRunResponse,
    RecipeRunsResponse,
    RunSubmissionResponse,
    RunSubmissionsResponse,
)
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.run_repository import RecipeRunRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.workspace_repository import WorkspaceRepository


class RecipeRunService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.workspace_repo = WorkspaceRepository()
        self.recipe_repo = RecipeRepository()
        self.run_repo = RecipeRunRepository()
        self.task_repo = TaskRepository()

    def create_recipe_run(self, workspace_slug: str, payload) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            version = self.recipe_repo.get_recipe_version_by_id(conn, payload.recipe_version_id)
            if not version:
                raise ValueError('recipe version not found')
            recipe = self.recipe_repo.get_recipe_by_id(conn, version.recipe_id)
            if not recipe or recipe.workspace_id != workspace.id:
                raise ValueError('recipe version does not belong to workspace')
            run = self.run_repo.create_recipe_run(
                conn,
                workspace_id=workspace.id,
                recipe_id=recipe.id,
                recipe_version_id=version.id,
                requested_by=payload.requested_by,
                parameters=payload.parameters,
            )
            env_vars = {**(version.env_template or {}), **(payload.parameters or {})}
            self.task_repo.create_task(
                conn,
                workspace_id=workspace.id,
                recipe_run_id=run.id,
                recipe_version_id=version.id,
                command=version.command,
                script_path=version.script_path,
                env_vars=env_vars,
                execution_spec={**(version.execution_spec or {}), 'recipeBody': version.recipe_body},
                timeout_seconds=version.timeout_seconds,
                task_kind=(version.execution_spec or {}).get('taskKind', 'generic_command'),
            )
            return self._response(run).to_api_dict()

    def list_recipe_runs(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            rows = self.run_repo.list_recipe_runs(conn, workspace.id)
            return RecipeRunsResponse(runs=[self._response(row) for row in rows]).to_api_dict()

    def get_recipe_run(self, run_id: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            row = self.run_repo.get_recipe_run_by_id(conn, run_id)
            return self._response(row).to_api_dict() if row else None

    def create_run_submission(self, workspace_slug: str, payload) -> dict:
        run = self.create_recipe_run(workspace_slug, payload)
        return {'submission': self._submission_from_api_dict(run)}

    def list_run_submissions(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            rows = self.run_repo.list_recipe_runs(conn, workspace.id)
            return RunSubmissionsResponse(
                submissions=[self._submission_response(row) for row in rows]
            ).to_api_dict()

    def get_run_submission(self, submission_id: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            row = self.run_repo.get_recipe_run_by_id(conn, submission_id)
            return {'submission': self._submission_response(row).to_api_dict()} if row else None

    @staticmethod
    def _response(row) -> RecipeRunResponse:
        return RecipeRunResponse(
            id=row.id,
            workspaceId=row.workspace_id,
            recipeId=row.recipe_id,
            recipeVersionId=row.recipe_version_id,
            requestedBy=row.requested_by,
            status=row.status,
            parameters=row.parameters,
            rootLineageNodeId=row.root_lineage_node_id,
            createdAt=row.created_at,
            startedAt=row.started_at,
            endedAt=row.ended_at,
            failureReason=row.failure_reason,
        )

    @staticmethod
    def _submission_response(row) -> RunSubmissionResponse:
        return RunSubmissionResponse(
            id=row.id,
            workspaceId=row.workspace_id,
            recipeId=row.recipe_id,
            recipeVersionId=row.recipe_version_id,
            requestedBy=row.requested_by,
            submissionKind='processing_pipeline',
            status=row.status,
            parameters=row.parameters,
            rootLineageNodeId=row.root_lineage_node_id,
            createdAt=row.created_at,
            startedAt=row.started_at,
            endedAt=row.ended_at,
            failureReason=row.failure_reason,
        )

    @staticmethod
    def _submission_from_api_dict(payload: dict) -> dict:
        return {
            'id': payload['id'],
            'workspaceId': payload['workspaceId'],
            'recipeId': payload['recipeId'],
            'recipeVersionId': payload['recipeVersionId'],
            'requestedBy': payload['requestedBy'],
            'submissionKind': 'processing_pipeline',
            'status': payload['status'],
            'parameters': payload.get('parameters', {}),
            'rootLineageNodeId': payload.get('rootLineageNodeId'),
            'createdAt': payload['createdAt'],
            'startedAt': payload.get('startedAt'),
            'endedAt': payload.get('endedAt'),
            'failureReason': payload.get('failureReason'),
        }
