from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.api.base import ApiModel


class WorkspaceCreateRequest(BaseModel):
    slug: str
    name: str
    description: str = ""
    owner_name: Optional[str] = Field(default=None, alias="ownerName")


class WorkspaceResponse(ApiModel):
    id: str
    slug: str
    name: str
    description: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class WorkspacesResponse(ApiModel):
    workspaces: list[WorkspaceResponse] = Field(default_factory=list)


class WorkspaceMemberAddRequest(BaseModel):
    user_name: str = Field(alias="userName")
    role: str = "MEMBER"


class WorkspaceMemberResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    user_name: str = Field(alias="userName")
    role: str
    created_at: datetime = Field(alias="createdAt")


class WorkspaceMembersResponse(ApiModel):
    members: list[WorkspaceMemberResponse] = Field(default_factory=list)


class RecipeCreateRequest(BaseModel):
    name: str
    description: str = ""
    owner_name: str = Field(alias="ownerName")
    recipe_body: dict[str, Any] = Field(default_factory=dict, alias="recipeBody")
    command: str
    script_path: str = Field(alias="scriptPath")
    parameter_schema: dict[str, Any] = Field(
        default_factory=dict, alias="parameterSchema"
    )
    env_template: dict[str, Any] = Field(default_factory=dict, alias="envTemplate")
    execution_spec: dict[str, Any] = Field(default_factory=dict, alias="executionSpec")
    timeout_seconds: int = Field(default=3600, alias="timeoutSeconds")


class RecipeVersionCreateRequest(BaseModel):
    created_by: str = Field(alias="createdBy")
    recipe_body: dict[str, Any] = Field(default_factory=dict, alias="recipeBody")
    command: str
    script_path: str = Field(alias="scriptPath")
    parameter_schema: dict[str, Any] = Field(
        default_factory=dict, alias="parameterSchema"
    )
    env_template: dict[str, Any] = Field(default_factory=dict, alias="envTemplate")
    execution_spec: dict[str, Any] = Field(default_factory=dict, alias="executionSpec")
    timeout_seconds: int = Field(default=3600, alias="timeoutSeconds")


class RecipeVersionResponse(ApiModel):
    id: str
    recipe_id: str = Field(alias="recipeId")
    version_number: int = Field(alias="versionNumber")
    recipe_body: dict[str, Any] = Field(alias="recipeBody")
    command: str
    script_path: str = Field(alias="scriptPath")
    parameter_schema: dict[str, Any] = Field(alias="parameterSchema")
    env_template: dict[str, Any] = Field(alias="envTemplate")
    execution_spec: dict[str, Any] = Field(alias="executionSpec")
    timeout_seconds: int = Field(alias="timeoutSeconds")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")


class RecipeResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    name: str
    description: str
    owner_name: str = Field(alias="ownerName")
    current_version_id: Optional[str] = Field(default=None, alias="currentVersionId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    current_version: Optional[RecipeVersionResponse] = Field(
        default=None, alias="currentVersion"
    )


class RecipesResponse(ApiModel):
    recipes: list[RecipeResponse] = Field(default_factory=list)


class RecipeVersionsResponse(ApiModel):
    versions: list[RecipeVersionResponse] = Field(default_factory=list)


class RunSubmissionCreateRequest(BaseModel):
    recipe_version_id: Optional[str] = Field(default=None, alias="recipeVersionId")
    name: Optional[str] = None
    requested_by: str = Field(alias="requestedBy")
    submission_kind: str = Field(default="processing_pipeline", alias="submissionKind")
    parameters: dict[str, Any] = Field(default_factory=dict)
    spec: dict[str, Any] = Field(default_factory=dict)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class RunSubmissionResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    recipe_id: Optional[str] = Field(default=None, alias="recipeId")
    recipe_version_id: Optional[str] = Field(default=None, alias="recipeVersionId")
    name: Optional[str] = None
    requested_by: str = Field(alias="requestedBy")
    submission_kind: str = Field(default="processing_pipeline", alias="submissionKind")
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    spec: dict[str, Any] = Field(default_factory=dict)
    root_lineage_node_id: Optional[str] = Field(default=None, alias="rootLineageNodeId")
    created_at: datetime = Field(alias="createdAt")
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    ended_at: Optional[datetime] = Field(default=None, alias="endedAt")
    failure_reason: Optional[str] = Field(default=None, alias="failureReason")


class RunSubmissionsResponse(ApiModel):
    submissions: list[RunSubmissionResponse] = Field(default_factory=list)


class WorkerRegisterRequest(BaseModel):
    worker_id: str = Field(alias="workerId")
    display_name: str = Field(alias="displayName")
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(default=1, alias="maxConcurrency")


class WorkerHeartbeatRequest(BaseModel):
    status: Optional[str] = None
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkerResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    display_name: str = Field(alias="displayName")
    status: str
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(alias="maxConcurrency")
    last_heartbeat_at: Optional[datetime] = Field(default=None, alias="lastHeartbeatAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class WorkersResponse(ApiModel):
    workers: list[WorkerResponse] = Field(default_factory=list)


class TaskClaimRequest(BaseModel):
    worker_id: str = Field(alias="workerId")
    supported_task_kinds: list[str] = Field(
        default_factory=list, alias="supportedTaskKinds"
    )


class TaskAttemptResponse(ApiModel):
    id: str
    task_id: str = Field(alias="taskId")
    worker_id: str = Field(alias="workerId")
    attempt_number: int = Field(alias="attemptNumber")
    status: str
    lease_token: str = Field(alias="leaseToken")
    openlineage_run_id: Optional[str] = Field(default=None, alias="openlineageRunId")
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    ended_at: Optional[datetime] = Field(default=None, alias="endedAt")
    last_heartbeat_at: Optional[datetime] = Field(default=None, alias="lastHeartbeatAt")
    failure_reason: Optional[str] = Field(default=None, alias="failureReason")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class TaskResponse(ApiModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    run_submission_id: str = Field(alias="runSubmissionId")
    recipe_version_id: Optional[str] = Field(default=None, alias="recipeVersionId")
    task_kind: str = Field(default="generic_command", alias="taskKind")
    status: str
    assigned_worker_id: Optional[str] = Field(default=None, alias="assignedWorkerId")
    current_attempt_id: Optional[str] = Field(default=None, alias="currentAttemptId")
    lease_token: Optional[str] = Field(default=None, alias="leaseToken")
    lease_expires_at: Optional[datetime] = Field(default=None, alias="leaseExpiresAt")
    attempt_count: int = Field(alias="attemptCount")
    command: str
    script_path: str = Field(alias="scriptPath")
    env_vars: dict[str, Any] = Field(default_factory=dict, alias="envVars")
    execution_spec: dict[str, Any] = Field(default_factory=dict, alias="executionSpec")
    timeout_seconds: int = Field(alias="timeoutSeconds")
    created_at: datetime = Field(alias="createdAt")
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    ended_at: Optional[datetime] = Field(default=None, alias="endedAt")
    failure_reason: Optional[str] = Field(default=None, alias="failureReason")
    current_attempt: Optional[TaskAttemptResponse] = Field(
        default=None, alias="currentAttempt"
    )


class TasksResponse(ApiModel):
    tasks: list[TaskResponse] = Field(default_factory=list)


class TaskClaimPayload(ApiModel):
    task_id: str = Field(alias="taskId")
    attempt_id: str = Field(alias="attemptId")
    lease_token: str = Field(alias="leaseToken")
    task_kind: str = Field(default="generic_command", alias="taskKind")
    submission: dict[str, Any] = Field(default_factory=dict)
    recipe_version: Optional[RecipeVersionResponse] = Field(
        default=None, alias="recipeVersion"
    )
    execution_spec: dict[str, Any] = Field(alias="executionSpec")
    env_vars: dict[str, Any] = Field(alias="envVars")
    command: str
    timeout_seconds: int = Field(alias="timeoutSeconds")


class TaskClaimResponse(ApiModel):
    claimed: bool
    task: Optional[TaskClaimPayload] = None


class TaskTransitionRequest(BaseModel):
    attempt_id: str = Field(alias="attemptId")
    lease_token: str = Field(alias="leaseToken")
    openlineage_run_id: Optional[str] = Field(default=None, alias="openlineageRunId")
    root_lineage_node_id: Optional[str] = Field(default=None, alias="rootLineageNodeId")
    failure_reason: Optional[str] = Field(default=None, alias="failureReason")


class TaskLogCreateRequest(BaseModel):
    stream: str
    message: str
    sequence: Optional[int] = None


class TaskArtifactCreateRequest(BaseModel):
    kind: str
    name: str
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dataset_id: Optional[str] = Field(default=None, alias="datasetId")
    dataset_version_id: Optional[str] = Field(default=None, alias="datasetVersionId")
    model_uri: Optional[str] = Field(default=None, alias="modelUri")


class TaskLogResponse(ApiModel):
    id: str
    attempt_id: str = Field(alias="attemptId")
    stream: str
    message: str
    sequence: int = 0
    logged_at: datetime = Field(alias="loggedAt")


class TaskLogsResponse(ApiModel):
    logs: list[TaskLogResponse] = Field(default_factory=list)


class TaskArtifactResponse(ApiModel):
    id: str
    attempt_id: str = Field(alias="attemptId")
    kind: str
    name: str
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dataset_id: Optional[str] = Field(default=None, alias="datasetId")
    dataset_version_id: Optional[str] = Field(default=None, alias="datasetVersionId")
    model_uri: Optional[str] = Field(default=None, alias="modelUri")
    created_at: datetime = Field(alias="createdAt")


class TaskArtifactsResponse(ApiModel):
    artifacts: list[TaskArtifactResponse] = Field(default_factory=list)
