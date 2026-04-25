from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class WorkspaceCreateRequest(BaseModel):
    slug: str
    name: str
    description: str = ''


class WorkspaceResponse(ApiModel):
    id: str
    slug: str
    name: str
    description: str
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')


class WorkspacesResponse(ApiModel):
    workspaces: list[WorkspaceResponse] = Field(default_factory=list)


class RecipeCreateRequest(BaseModel):
    name: str
    description: str = ''
    owner_name: str
    recipe_body: dict[str, Any] = Field(default_factory=dict)
    command: str
    script_path: str
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    env_template: dict[str, Any] = Field(default_factory=dict)
    execution_spec: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 3600
    lineage_namespace: Optional[str] = None
    lineage_job_name: Optional[str] = None


class RecipeVersionCreateRequest(BaseModel):
    created_by: str
    recipe_body: dict[str, Any] = Field(default_factory=dict)
    command: str
    script_path: str
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    env_template: dict[str, Any] = Field(default_factory=dict)
    execution_spec: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 3600
    lineage_namespace: Optional[str] = None
    lineage_job_name: Optional[str] = None


class RecipeVersionResponse(ApiModel):
    id: str
    recipe_id: str = Field(alias='recipeId')
    version_number: int = Field(alias='versionNumber')
    recipe_body: dict[str, Any] = Field(alias='recipeBody')
    command: str
    script_path: str = Field(alias='scriptPath')
    parameter_schema: dict[str, Any] = Field(alias='parameterSchema')
    env_template: dict[str, Any] = Field(alias='envTemplate')
    execution_spec: dict[str, Any] = Field(alias='executionSpec')
    timeout_seconds: int = Field(alias='timeoutSeconds')
    lineage_namespace: Optional[str] = Field(default=None, alias='lineageNamespace')
    lineage_job_name: Optional[str] = Field(default=None, alias='lineageJobName')
    created_by: str = Field(alias='createdBy')
    created_at: datetime = Field(alias='createdAt')


class RecipeResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias='workspaceId')
    name: str
    description: str
    owner_name: str = Field(alias='ownerName')
    current_version_id: Optional[str] = Field(default=None, alias='currentVersionId')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    current_version: Optional[RecipeVersionResponse] = Field(default=None, alias='currentVersion')


class RecipesResponse(ApiModel):
    recipes: list[RecipeResponse] = Field(default_factory=list)


class RecipeVersionsResponse(ApiModel):
    versions: list[RecipeVersionResponse] = Field(default_factory=list)


class RecipeRunCreateRequest(BaseModel):
    recipe_version_id: str = Field(alias='recipeVersionId')
    requested_by: str = Field(alias='requestedBy')
    parameters: dict[str, Any] = Field(default_factory=dict)


class RunSubmissionCreateRequest(RecipeRunCreateRequest):
    submission_kind: str = Field(default='processing_pipeline', alias='submissionKind')
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class RecipeRunResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias='workspaceId')
    recipe_id: str = Field(alias='recipeId')
    recipe_version_id: str = Field(alias='recipeVersionId')
    requested_by: str = Field(alias='requestedBy')
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    root_lineage_node_id: Optional[str] = Field(default=None, alias='rootLineageNodeId')
    created_at: datetime = Field(alias='createdAt')
    started_at: Optional[datetime] = Field(default=None, alias='startedAt')
    ended_at: Optional[datetime] = Field(default=None, alias='endedAt')
    failure_reason: Optional[str] = Field(default=None, alias='failureReason')


class RecipeRunsResponse(ApiModel):
    runs: list[RecipeRunResponse] = Field(default_factory=list)


class RunSubmissionResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias='workspaceId')
    recipe_id: str = Field(alias='recipeId')
    recipe_version_id: str = Field(alias='recipeVersionId')
    requested_by: str = Field(alias='requestedBy')
    submission_kind: str = Field(default='processing_pipeline', alias='submissionKind')
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    root_lineage_node_id: Optional[str] = Field(default=None, alias='rootLineageNodeId')
    created_at: datetime = Field(alias='createdAt')
    started_at: Optional[datetime] = Field(default=None, alias='startedAt')
    ended_at: Optional[datetime] = Field(default=None, alias='endedAt')
    failure_reason: Optional[str] = Field(default=None, alias='failureReason')


class RunSubmissionsResponse(ApiModel):
    submissions: list[RunSubmissionResponse] = Field(default_factory=list)


class WorkerRegisterRequest(BaseModel):
    worker_id: str = Field(alias='workerId')
    display_name: str = Field(alias='displayName')
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(default=1, alias='maxConcurrency')


class WorkerHeartbeatRequest(BaseModel):
    status: Optional[str] = None
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkerResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias='workspaceId')
    display_name: str = Field(alias='displayName')
    status: str
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(alias='maxConcurrency')
    last_heartbeat_at: Optional[datetime] = Field(default=None, alias='lastHeartbeatAt')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')


class WorkersResponse(ApiModel):
    workers: list[WorkerResponse] = Field(default_factory=list)


class TaskClaimRequest(BaseModel):
    worker_id: str = Field(alias='workerId')
    supported_task_kinds: list[str] = Field(default_factory=list, alias='supportedTaskKinds')


class TaskAttemptResponse(ApiModel):
    id: str
    task_id: str = Field(alias='taskId')
    worker_id: str = Field(alias='workerId')
    attempt_number: int = Field(alias='attemptNumber')
    status: str
    lease_token: str = Field(alias='leaseToken')
    openlineage_run_id: Optional[str] = Field(default=None, alias='openlineageRunId')
    mlflow_run_id: Optional[str] = Field(default=None, alias='mlflowRunId')
    started_at: Optional[datetime] = Field(default=None, alias='startedAt')
    ended_at: Optional[datetime] = Field(default=None, alias='endedAt')
    last_heartbeat_at: Optional[datetime] = Field(default=None, alias='lastHeartbeatAt')
    failure_reason: Optional[str] = Field(default=None, alias='failureReason')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')


class TaskResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias='workspaceId')
    recipe_run_id: str = Field(alias='recipeRunId')
    recipe_version_id: str = Field(alias='recipeVersionId')
    task_kind: str = Field(default='generic_command', alias='taskKind')
    status: str
    assigned_worker_id: Optional[str] = Field(default=None, alias='assignedWorkerId')
    current_attempt_id: Optional[str] = Field(default=None, alias='currentAttemptId')
    lease_token: Optional[str] = Field(default=None, alias='leaseToken')
    lease_expires_at: Optional[datetime] = Field(default=None, alias='leaseExpiresAt')
    attempt_count: int = Field(alias='attemptCount')
    command: str
    script_path: str = Field(alias='scriptPath')
    env_vars: dict[str, Any] = Field(default_factory=dict, alias='envVars')
    execution_spec: dict[str, Any] = Field(default_factory=dict, alias='executionSpec')
    timeout_seconds: int = Field(alias='timeoutSeconds')
    created_at: datetime = Field(alias='createdAt')
    started_at: Optional[datetime] = Field(default=None, alias='startedAt')
    ended_at: Optional[datetime] = Field(default=None, alias='endedAt')
    failure_reason: Optional[str] = Field(default=None, alias='failureReason')
    current_attempt: Optional[TaskAttemptResponse] = Field(default=None, alias='currentAttempt')


class TasksResponse(ApiModel):
    tasks: list[TaskResponse] = Field(default_factory=list)


class TaskClaimPayload(ApiModel):
    task_id: str = Field(alias='taskId')
    attempt_id: str = Field(alias='attemptId')
    lease_token: str = Field(alias='leaseToken')
    task_kind: str = Field(default='generic_command', alias='taskKind')
    submission: dict[str, Any] = Field(default_factory=dict)
    recipe_version: RecipeVersionResponse = Field(alias='recipeVersion')
    execution_spec: dict[str, Any] = Field(alias='executionSpec')
    env_vars: dict[str, Any] = Field(alias='envVars')
    command: str
    timeout_seconds: int = Field(alias='timeoutSeconds')


class TaskClaimResponse(ApiModel):
    claimed: bool
    task: Optional[TaskClaimPayload] = None


class TaskTransitionRequest(BaseModel):
    attempt_id: str = Field(alias='attemptId')
    lease_token: str = Field(alias='leaseToken')
    openlineage_run_id: Optional[str] = Field(default=None, alias='openlineageRunId')
    mlflow_run_id: Optional[str] = Field(default=None, alias='mlflowRunId')
    root_lineage_node_id: Optional[str] = Field(default=None, alias='rootLineageNodeId')
    failure_reason: Optional[str] = Field(default=None, alias='failureReason')


class TaskLogCreateRequest(BaseModel):
    stream: str
    message: str
    sequence: Optional[int] = None


class TaskArtifactCreateRequest(BaseModel):
    kind: str
    name: str
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dataset_id: Optional[str] = Field(default=None, alias='datasetId')
    dataset_version_id: Optional[str] = Field(default=None, alias='datasetVersionId')
    model_uri: Optional[str] = Field(default=None, alias='modelUri')


class TaskLogResponse(ApiModel):
    id: str
    attempt_id: str = Field(alias='attemptId')
    stream: str
    message: str
    sequence: int = 0
    logged_at: datetime = Field(alias='loggedAt')


class TaskLogsResponse(ApiModel):
    logs: list[TaskLogResponse] = Field(default_factory=list)


class TaskArtifactResponse(ApiModel):
    id: str
    attempt_id: str = Field(alias='attemptId')
    kind: str
    name: str
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dataset_id: Optional[str] = Field(default=None, alias='datasetId')
    dataset_version_id: Optional[str] = Field(default=None, alias='datasetVersionId')
    model_uri: Optional[str] = Field(default=None, alias='modelUri')
    created_at: datetime = Field(alias='createdAt')


class TaskArtifactsResponse(ApiModel):
    artifacts: list[TaskArtifactResponse] = Field(default_factory=list)
