from __future__ import annotations

from typing import Optional

from sqlalchemy.engine import Engine

from dj_panel.app.execution.definitions import DEFAULT_DJ_COMMAND, DEFAULT_DJ_CONFIG_ARG
from dj_panel.app.models.api import ProcessingRunSpec, RunSubmissionResponse, RunSubmissionsResponse
from dj_panel.app.models.constant import AssetKind, RunSubmissionKind, RunSubmissionStatus, TaskKind, TaskStatus
from dj_panel.app.repositories.assets import AssetRepository
from dj_panel.app.repositories.recipes import RecipeRepository
from dj_panel.app.repositories.run_submissions import RunSubmissionRepository
from dj_panel.app.repositories.tasks import TaskRepository
from dj_panel.app.repositories.workspaces import WorkspaceRepository
from dj_panel.app.utils.common_utils import utc_now


class RunSubmissionService:
    CANCELLED_BY_USER_REASON = "Cancelled by user"

    def __init__(self, engine: Engine):
        self.engine = engine
        self.workspace_repo = WorkspaceRepository()
        self.asset_repo = AssetRepository()
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

            processing_spec_payload = dict(payload.spec or {})
            if processing_spec_payload.get("process"):
                submission = self._create_processing_submission_from_spec(
                    conn, workspace.id, workspace_slug, payload
                )
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

    def resume_run_submission(self, submission_id: str) -> dict:
        with self.engine.begin() as conn:
            submission = self.submission_repo.get_run_submission_by_id(conn, submission_id)
            if not submission:
                raise ValueError("run submission not found")
            if submission.status not in {
                RunSubmissionStatus.FAILED.value,
                RunSubmissionStatus.CANCELLED.value,
            }:
                raise RuntimeError(
                    f"run submission {submission_id} cannot be resumed from status {submission.status}"
                )

            task = self.task_repo.get_task_by_run_submission_id(conn, submission.id)
            if not task:
                raise ValueError("task not found for run submission")
            if task.status not in {
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            }:
                raise RuntimeError(
                    f"task {task.id} cannot be resumed from status {task.status}"
                )

            self.task_repo.reset_task_for_resume(conn, task.id)
            submission = self.submission_repo.reset_run_submission_for_resume(
                conn, submission.id
            )
            return {"submission": self._response(submission).to_api_dict()}

    def cancel_run_submission(self, submission_id: str) -> dict:
        with self.engine.begin() as conn:
            submission = self.submission_repo.get_run_submission_by_id(conn, submission_id)
            if not submission:
                raise ValueError("run submission not found")
            if submission.status != RunSubmissionStatus.PENDING.value:
                raise RuntimeError(
                    f"run submission {submission_id} cannot be cancelled from status {submission.status}"
                )

            task = self.task_repo.get_task_by_run_submission_id(conn, submission.id)
            if not task:
                raise ValueError("task not found for run submission")
            if task.status != TaskStatus.PENDING.value:
                raise RuntimeError(
                    f"task {task.id} cannot be cancelled from status {task.status}"
                )

            self.task_repo.cancel_pending_task(
                conn, task.id, self.CANCELLED_BY_USER_REASON
            )
            submission = self.submission_repo.update_run_submission_status(
                conn,
                submission.id,
                RunSubmissionStatus.CANCELLED.value,
                ended_at=utc_now(),
                failure_reason=self.CANCELLED_BY_USER_REASON,
            )
            return {"submission": self._response(submission).to_api_dict()}

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

    def _create_processing_submission_from_spec(
        self, conn, workspace_id: str, workspace_slug: str, payload
    ):
        processing = ProcessingRunSpec.model_validate(payload.spec or {})
        process_spec = processing.process
        dj_configs = process_spec.dj_configs
        dataset_inputs = list((process_spec.datasets.inputs if process_spec.datasets else []))
        if dataset_inputs:
            if "dataset" in (process_spec.extra_configs or {}):
                raise ValueError(
                    "process.datasets.inputs cannot be used together with process.extra_configs.dataset"
                )
            if "dataset_path" in (process_spec.extra_configs or {}):
                raise ValueError(
                    "process.datasets.inputs cannot be used together with process.extra_configs.dataset_path"
                )
            if "dataset" in (payload.parameters or {}):
                raise ValueError(
                    "process.datasets.inputs cannot be used together with parameters.dataset"
                )
            if "dataset_path" in (payload.parameters or {}):
                raise ValueError(
                    "process.datasets.inputs cannot be used together with parameters.dataset_path"
                )
        processing_parameters = {
            **dict(process_spec.extra_configs or {}),
            **dict(payload.parameters or {}),
        }
        if dataset_inputs:
            processing_parameters["dataset"] = {
                "configs": [
                    self._resolve_processing_dataset_input(
                        conn, dataset_ref.namespace, dataset_ref.name
                    )
                    for dataset_ref in dataset_inputs
                ]
            }
        env_vars = {str(key): value for key, value in (process_spec.env or {}).items()}
        timeout_seconds = process_spec.timeout_seconds or 7200

        if dj_configs.mode == "workspace_recipe":
            if not dj_configs.name:
                raise ValueError("workspace_recipe processing spec requires recipe name")
            recipe = self.recipe_repo.get_recipe_by_name(conn, workspace_id, dj_configs.name)
            if not recipe:
                raise ValueError(
                    f"recipe not found in workspace {workspace_slug!r}: {dj_configs.name}"
                )
            version = (
                self.recipe_repo.get_recipe_version_by_id(conn, dj_configs.version_id)
                if dj_configs.version_id
                else self.recipe_repo.get_recipe_version_by_id(
                    conn, recipe.current_version_id
                )
                )
            if not version or version.recipe_id != recipe.id:
                raise ValueError("recipe version not found for workspace recipe")
            submission = self.submission_repo.create_run_submission(
                conn,
                workspace_id=workspace_id,
                recipe_id=recipe.id,
                recipe_version_id=version.id,
                name=payload.name or processing.name,
                requested_by=payload.requested_by,
                submission_kind=payload.submission_kind,
                parameters=processing_parameters,
                spec=payload.spec or {},
            )
            task_env = {
                **(version.env_template or {}),
                **processing_parameters,
                **env_vars,
            }
            self.task_repo.create_task(
                conn,
                workspace_id=workspace_id,
                run_submission_id=submission.id,
                recipe_version_id=version.id,
                command=version.command,
                script_path=version.script_path,
                env_vars=task_env,
                execution_spec={
                    **(version.execution_spec or {}),
                    "recipeBody": version.recipe_body,
                    "submissionSpec": payload.spec or {},
                },
                timeout_seconds=process_spec.timeout_seconds or version.timeout_seconds,
                task_kind=(version.execution_spec or {}).get(
                    "taskKind", TaskKind.DJ_RECIPE.value
                ),
            )
            return submission

        recipe_body = dict(dj_configs.recipe_body or {})
        if not recipe_body:
            raise ValueError("local_file processing spec requires recipeBody")
        submission = self.submission_repo.create_run_submission(
            conn,
            workspace_id=workspace_id,
            recipe_id=None,
            recipe_version_id=None,
            name=payload.name or processing.name,
            requested_by=payload.requested_by,
            submission_kind=payload.submission_kind,
            parameters=processing_parameters,
            spec=payload.spec or {},
        )
        self.task_repo.create_task(
            conn,
            workspace_id=workspace_id,
            run_submission_id=submission.id,
            recipe_version_id=None,
            command=DEFAULT_DJ_COMMAND,
            script_path=str(dj_configs.path or ""),
            env_vars=env_vars,
            execution_spec={
                "taskKind": TaskKind.DJ_RECIPE.value,
                "configArg": DEFAULT_DJ_CONFIG_ARG,
                "extraArgs": [],
                "recipeBody": recipe_body,
                "submissionSpec": payload.spec or {},
            },
            timeout_seconds=timeout_seconds,
            task_kind=TaskKind.DJ_RECIPE.value,
        )
        return submission

    def _resolve_processing_dataset_input(
        self, conn, namespace: str, name: str
    ) -> dict:
        asset = self.asset_repo.get_asset_by_name(conn, namespace, name, AssetKind.DATASET)
        if not asset:
            raise ValueError(f"dataset not found: {namespace}/{name}")
        facets = asset.facets or {}
        datajuicer_input = facets.get("datajuicerInput")
        if not isinstance(datajuicer_input, dict):
            raise ValueError(
                f"dataset {namespace}/{name} is missing facets.datajuicerInput.inputConfig"
            )
        input_config = datajuicer_input.get("inputConfig")
        if not isinstance(input_config, dict) or not input_config:
            raise ValueError(
                f"dataset {namespace}/{name} is missing facets.datajuicerInput.inputConfig"
            )
        if "dataset" in input_config or "configs" in input_config:
            raise ValueError(
                f"dataset {namespace}/{name} facets.datajuicerInput.inputConfig must be a single dataset config item"
            )
        return dict(input_config)
