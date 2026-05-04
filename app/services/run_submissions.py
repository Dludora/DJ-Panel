from __future__ import annotations

from typing import Optional

from sqlalchemy.engine import Engine

from app.models.api import RunSubmissionResponse, RunSubmissionsResponse
from app.models.constant import RunSubmissionKind, TaskKind
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

            if payload.submission_kind in {
                RunSubmissionKind.TRAINING,
                RunSubmissionKind.EVALUATION,
            }:
                submission = self._create_command_submission(conn, workspace.id, payload)
                return {"submission": self._response(submission).to_api_dict()}

            if not payload.recipe_version_id:
                raise ValueError("recipe version is required for processing submissions")

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
                name=payload.name,
                requested_by=payload.requested_by,
                submission_kind=payload.submission_kind,
                parameters=payload.parameters,
                spec=payload.spec or {},
            )

            submission_env = dict((payload.spec or {}).get("env") or {})
            env_vars = {
                **(version.env_template or {}),
                **(payload.parameters or {}),
                **submission_env,
            }
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
                task_kind=(version.execution_spec or {}).get(
                    "taskKind", TaskKind.DJ_RECIPE.value
                ),
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
            name=row.name,
            requestedBy=row.requested_by,
            submissionKind=row.submission_kind,
            status=row.status,
            parameters=row.parameters,
            spec=row.spec,
            rootLineageNodeId=row.root_lineage_node_id,
            createdAt=row.created_at,
            startedAt=row.started_at,
            endedAt=row.ended_at,
            failureReason=row.failure_reason,
        )

    def _create_command_submission(self, conn, workspace_id: str, payload):
        spec = dict(payload.spec or {})
        command = str(spec.get("command") or "").strip()
        if not command:
            raise ValueError("command spec requires a non-empty command")
        workdir = str(spec.get("workdir") or "").strip()
        env = spec.get("env") or {}
        if not isinstance(env, dict):
            raise ValueError("command spec env must be an object")
        timeout_seconds = int(
            spec.get("timeoutSeconds", spec.get("timeout_seconds", 7200))
        )
        submission = self.submission_repo.create_run_submission(
            conn,
            workspace_id=workspace_id,
            recipe_id=None,
            recipe_version_id=None,
            name=payload.name or spec.get("name"),
            requested_by=payload.requested_by,
            submission_kind=payload.submission_kind,
            parameters=payload.parameters,
            spec=spec,
        )
        self.task_repo.create_task(
            conn,
            workspace_id=workspace_id,
            run_submission_id=submission.id,
            recipe_version_id=None,
            command=command,
            script_path=workdir,
            env_vars={str(key): value for key, value in env.items()},
            execution_spec={
                "workdir": workdir,
                "submissionSpec": spec,
                "inputs": payload.inputs,
                "outputs": payload.outputs,
            },
            timeout_seconds=timeout_seconds,
            task_kind=payload.submission_kind.value,
        )
        return submission
