from __future__ import annotations

from sqlalchemy.engine import Engine
from typing import Optional

from app.models.api.control_plane import (
    TaskArtifactResponse,
    TaskArtifactsResponse,
    TaskAttemptResponse,
    TaskClaimPayload,
    TaskClaimResponse,
    TaskLogResponse,
    TaskLogsResponse,
    TaskResponse,
    TasksResponse,
)
from app.models.types.control_plane import RunSubmissionStatus, TaskAttemptStatus, TaskStatus
from app.repositories.recipes import RecipeRepository
from app.repositories.run_submissions import RunSubmissionRepository
from app.repositories.tasks import TaskRepository
from app.repositories.workers import WorkerRepository
from app.repositories.workspaces import WorkspaceRepository


class TaskService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.workspace_repo = WorkspaceRepository()
        self.recipe_repo = RecipeRepository()
        self.submission_repo = RunSubmissionRepository()
        self.task_repo = TaskRepository()
        self.worker_repo = WorkerRepository()

    def list_tasks(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            tasks = self.task_repo.list_tasks(conn, workspace.id)
            return TasksResponse(tasks=[self._task_response(conn, task) for task in tasks]).to_api_dict()

    def get_task(self, task_id: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            task = self.task_repo.get_task_by_id(conn, task_id)
            return self._task_response(conn, task).to_api_dict() if task else None

    def claim_task(self, workspace_slug: str, worker_id: str, supported_task_kinds: list[str] | None = None) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            worker = self.worker_repo.get_worker_by_id(conn, worker_id)
            if not worker or worker.workspace_id != workspace.id:
                raise ValueError('worker not found in workspace')
            claimed = self.task_repo.claim_next_task(conn, workspace.id, worker_id, supported_task_kinds)
            if not claimed:
                return TaskClaimResponse(claimed=False, task=None).to_api_dict()
            task, attempt = claimed
            version = self.recipe_repo.get_recipe_version_by_id(conn, task.recipe_version_id) if task.recipe_version_id else None
            submission = self.submission_repo.get_run_submission_by_id(conn, task.run_submission_id)
            payload = TaskClaimPayload(
                taskId=task.id,
                attemptId=attempt.id,
                leaseToken=attempt.lease_token,
                taskKind=task.task_kind,
                submission=self._submission_payload(submission, task),
                recipeVersion=self._recipe_version_response(version),
                executionSpec=task.execution_spec,
                envVars=task.env_vars,
                command=task.command,
                timeoutSeconds=task.timeout_seconds,
            )
            self.submission_repo.update_run_submission_status(conn, task.run_submission_id, RunSubmissionStatus.CLAIMED.value)
            return TaskClaimResponse(claimed=True, task=payload).to_api_dict()

    def start_task(self, task_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            task, attempt = self.task_repo.transition_task(
                conn,
                task_id,
                payload.attempt_id,
                payload.lease_token,
                task_status=TaskStatus.RUNNING,
                attempt_status=TaskAttemptStatus.RUNNING,
                openlineage_run_id=payload.openlineage_run_id,
                mark_started=True,
            )
            self.submission_repo.update_run_submission_status(
                conn,
                task.run_submission_id,
                RunSubmissionStatus.RUNNING.value,
                started_at=task.started_at,
                root_lineage_node_id=payload.root_lineage_node_id,
            )
            return self._task_response(conn, task, attempt).to_api_dict()

    def complete_task(self, task_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            task, attempt = self.task_repo.transition_task(
                conn,
                task_id,
                payload.attempt_id,
                payload.lease_token,
                task_status=TaskStatus.SUCCEEDED,
                attempt_status=TaskAttemptStatus.SUCCEEDED,
                openlineage_run_id=payload.openlineage_run_id,
                mark_ended=True,
            )
            self.submission_repo.update_run_submission_status(
                conn,
                task.run_submission_id,
                RunSubmissionStatus.SUCCEEDED.value,
                ended_at=task.ended_at,
                root_lineage_node_id=payload.root_lineage_node_id,
            )
            return self._task_response(conn, task, attempt).to_api_dict()

    def fail_task(self, task_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            task, attempt = self.task_repo.transition_task(
                conn,
                task_id,
                payload.attempt_id,
                payload.lease_token,
                task_status=TaskStatus.FAILED,
                attempt_status=TaskAttemptStatus.FAILED,
                openlineage_run_id=payload.openlineage_run_id,
                failure_reason=payload.failure_reason,
                mark_ended=True,
            )
            self.submission_repo.update_run_submission_status(
                conn,
                task.run_submission_id,
                RunSubmissionStatus.FAILED.value,
                ended_at=task.ended_at,
                failure_reason=payload.failure_reason,
                root_lineage_node_id=payload.root_lineage_node_id,
            )
            return self._task_response(conn, task, attempt).to_api_dict()

    def cancel_task(self, task_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            task, attempt = self.task_repo.transition_task(
                conn,
                task_id,
                payload.attempt_id,
                payload.lease_token,
                task_status=TaskStatus.CANCELLED,
                attempt_status=TaskAttemptStatus.CANCELLED,
                failure_reason=payload.failure_reason,
                mark_ended=True,
            )
            self.submission_repo.update_run_submission_status(
                conn,
                task.run_submission_id,
                RunSubmissionStatus.CANCELLED.value,
                ended_at=task.ended_at,
                failure_reason=payload.failure_reason,
                root_lineage_node_id=payload.root_lineage_node_id,
            )
            return self._task_response(conn, task, attempt).to_api_dict()

    def create_log(self, attempt_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            attempt = self.task_repo.update_attempt_heartbeat(conn, attempt_id)
            log = self.task_repo.create_task_log(conn, attempt.id, payload.stream, payload.message, payload.sequence)
            return TaskLogResponse(**log).to_api_dict()

    def list_logs(self, attempt_id: str) -> dict:
        with self.engine.begin() as conn:
            logs = self.task_repo.list_task_logs(conn, attempt_id)
            return TaskLogsResponse(logs=[TaskLogResponse(**log) for log in logs]).to_api_dict()

    def create_artifact(self, attempt_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            attempt = self.task_repo.update_attempt_heartbeat(conn, attempt_id)
            artifact = self.task_repo.create_task_artifact(
                conn,
                attempt.id,
                payload.kind,
                payload.name,
                payload.uri,
                payload.metadata,
                payload.dataset_id,
                payload.dataset_version_id,
                payload.model_uri,
            )
            return TaskArtifactResponse(**artifact).to_api_dict()

    def list_artifacts(self, attempt_id: str) -> dict:
        with self.engine.begin() as conn:
            artifacts = self.task_repo.list_task_artifacts(conn, attempt_id)
            return TaskArtifactsResponse(artifacts=[TaskArtifactResponse(**artifact) for artifact in artifacts]).to_api_dict()

    def _task_response(self, conn, task, attempt=None) -> TaskResponse:
        attempt = attempt or (self.task_repo.get_attempt_by_id(conn, task.current_attempt_id) if task.current_attempt_id else None)
        return TaskResponse(
            id=task.id,
            workspaceId=task.workspace_id,
            runSubmissionId=task.run_submission_id,
            recipeVersionId=task.recipe_version_id,
            taskKind=task.task_kind,
            status=task.status,
            assignedWorkerId=task.assigned_worker_id,
            currentAttemptId=task.current_attempt_id,
            leaseToken=task.lease_token,
            leaseExpiresAt=task.lease_expires_at,
            attemptCount=task.attempt_count,
            command=task.command,
            scriptPath=task.script_path,
            envVars=task.env_vars,
            executionSpec=task.execution_spec,
            timeoutSeconds=task.timeout_seconds,
            createdAt=task.created_at,
            startedAt=task.started_at,
            endedAt=task.ended_at,
            failureReason=task.failure_reason,
            currentAttempt=self._attempt_response(attempt) if attempt else None,
        )

    @staticmethod
    def _submission_payload(submission, task) -> dict:
        if not submission:
            return {
                'id': task.run_submission_id,
                'workspaceId': task.workspace_id,
                'submissionKind': task.task_kind,
                'parameters': {},
                'spec': {},
            }
        return {
            'id': submission.id,
            'workspaceId': submission.workspace_id,
            'recipeId': submission.recipe_id,
            'recipeVersionId': submission.recipe_version_id,
            'name': submission.name,
            'requestedBy': submission.requested_by,
            'submissionKind': submission.submission_kind,
            'status': submission.status,
            'parameters': submission.parameters,
            'spec': submission.spec,
            'rootLineageNodeId': submission.root_lineage_node_id,
            'createdAt': submission.created_at,
            'startedAt': submission.started_at,
            'endedAt': submission.ended_at,
            'failureReason': submission.failure_reason,
        }

    @staticmethod
    def _attempt_response(attempt) -> TaskAttemptResponse:
        return TaskAttemptResponse(
            id=attempt.id,
            taskId=attempt.task_id,
            workerId=attempt.worker_id,
            attemptNumber=attempt.attempt_number,
            status=attempt.status,
            leaseToken=attempt.lease_token,
            openlineageRunId=attempt.openlineage_run_id,
            startedAt=attempt.started_at,
            endedAt=attempt.ended_at,
            lastHeartbeatAt=attempt.last_heartbeat_at,
            failureReason=attempt.failure_reason,
            createdAt=attempt.created_at,
            updatedAt=attempt.updated_at,
        )

    @staticmethod
    def _recipe_version_response(version):
        from app.models.api.control_plane import RecipeVersionResponse

        if version is None:
            return None
        return RecipeVersionResponse(
            id=version.id,
            recipeId=version.recipe_id,
            versionNumber=version.version_number,
            recipeBody=version.recipe_body,
            command=version.command,
            scriptPath=version.script_path,
            parameterSchema=version.parameter_schema,
            envTemplate=version.env_template,
            executionSpec=version.execution_spec,
            timeoutSeconds=version.timeout_seconds,
            createdBy=version.created_by,
            createdAt=version.created_at,
        )
