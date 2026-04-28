from __future__ import annotations

from typing import Optional

from sqlalchemy.engine import Engine

from app.models.api.control_plane import RunSubmissionResponse, RunSubmissionsResponse
from app.repositories.recipes import RecipeRepository
from app.repositories.run_submissions import RunSubmissionRepository
from app.repositories.tasks import TaskRepository
from app.repositories.workspaces import WorkspaceRepository


class RunSubmissionService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.workspace_repo = WorkspaceRepository()
        self.recipe_repo = RecipeRepository()
        self.submission_repo = RunSubmissionRepository()
        self.task_repo = TaskRepository()

    def create_run_submission(self, workspace_slug: str, payload) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError("workspace not found")

            version = self.recipe_repo.get_recipe_version_by_id(
                conn, payload.recipe_version_id
            )
            if not version:
                raise ValueError("recipe version not found")

            recipe = self.recipe_repo.get_recipe_by_id(conn, version.recipe_id)
            if not recipe or recipe.workspace_id != workspace.id:
                raise ValueError("recipe version does not belong to workspace")

            submission = self.submission_repo.create_run_submission(
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
                run_submission_id=submission.id,
                recipe_version_id=version.id,
                command=version.command,
                script_path=version.script_path,
                env_vars=env_vars,
                execution_spec={
                    **(version.execution_spec or {}),
                    "recipeBody": version.recipe_body,
                },
                timeout_seconds=version.timeout_seconds,
                task_kind=(version.execution_spec or {}).get("taskKind", "dj_recipe"),
            )

            return {"submission": self._response(submission).to_api_dict()}

    def list_run_submissions(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError("workspace not found")
            rows = self.submission_repo.list_run_submissions(conn, workspace.id)
            return RunSubmissionsResponse(
                submissions=[self._response(row) for row in rows]
            ).to_api_dict()

    def get_run_submission(self, submission_id: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            row = self.submission_repo.get_run_submission_by_id(conn, submission_id)
            if not row:
                return None
            return {"submission": self._response(row).to_api_dict()}

    @staticmethod
    def _response(row) -> RunSubmissionResponse:
        return RunSubmissionResponse(
            id=row.id,
            workspaceId=row.workspace_id,
            recipeId=row.recipe_id,
            recipeVersionId=row.recipe_version_id,
            requestedBy=row.requested_by,
            submissionKind="processing_pipeline",
            status=row.status,
            parameters=row.parameters,
            rootLineageNodeId=row.root_lineage_node_id,
            createdAt=row.created_at,
            startedAt=row.started_at,
            endedAt=row.ended_at,
            failureReason=row.failure_reason,
        )
