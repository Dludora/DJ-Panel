from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.constant import RunSubmissionKind, TaskKind


class RequestModel(BaseModel):
    pass


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class IngestionStatus(str, Enum):
    ACCEPTED = "accepted"


class WorkspaceCreateRequest(RequestModel):
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


class WorkspaceMemberAddRequest(RequestModel):
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


class RecipeCreateRequest(RequestModel):
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


class RecipeVersionCreateRequest(RequestModel):
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


class RunSubmissionCreateRequest(RequestModel):
    recipe_version_id: Optional[str] = Field(default=None, alias="recipeVersionId")
    name: Optional[str] = None
    requested_by: str = Field(alias="requestedBy")
    submission_kind: RunSubmissionKind = Field(
        default=RunSubmissionKind.PROCESSING_PIPELINE, alias="submissionKind"
    )
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
    submission_kind: RunSubmissionKind = Field(
        default=RunSubmissionKind.PROCESSING_PIPELINE, alias="submissionKind"
    )
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


class WorkerRegisterRequest(RequestModel):
    worker_id: str = Field(alias="workerId")
    display_name: str = Field(alias="displayName")
    labels: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(default=1, alias="maxConcurrency")


class WorkerHeartbeatRequest(RequestModel):
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


class TaskClaimRequest(RequestModel):
    worker_id: str = Field(alias="workerId")
    supported_task_kinds: list[TaskKind] = Field(
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
    task_kind: TaskKind = Field(default=TaskKind.GENERIC_COMMAND, alias="taskKind")
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
    task_kind: TaskKind = Field(default=TaskKind.GENERIC_COMMAND, alias="taskKind")
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


class TaskTransitionRequest(RequestModel):
    attempt_id: str = Field(alias="attemptId")
    lease_token: str = Field(alias="leaseToken")
    openlineage_run_id: Optional[str] = Field(default=None, alias="openlineageRunId")
    root_lineage_node_id: Optional[str] = Field(default=None, alias="rootLineageNodeId")
    failure_reason: Optional[str] = Field(default=None, alias="failureReason")


class TaskArtifactCreateRequest(RequestModel):
    kind: str
    name: str
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    dataset_id: Optional[str] = Field(default=None, alias="datasetId")
    dataset_version_id: Optional[str] = Field(default=None, alias="datasetVersionId")
    model_uri: Optional[str] = Field(default=None, alias="modelUri")


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


class NamespaceName(ApiModel):
    namespace: str
    name: str


class VersionedNamespaceName(NamespaceName):
    version: str


class NamespaceModel(ApiModel):
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    owner_name: str = Field(alias="ownerName")
    description: str
    is_hidden: bool = Field(alias="isHidden")


class FieldModel(ApiModel):
    name: str
    type: str | None = None
    tags: list[Any] = Field(default_factory=list)
    description: str = ""


class TagModel(ApiModel):
    name: str
    description: str


class JobVersionName(ApiModel):
    name: str
    namespace: str
    version: str


class RunModel(ApiModel):
    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    nominal_start_time: datetime | None = Field(alias="nominalStartTime")
    nominal_end_time: datetime | None = Field(alias="nominalEndTime")
    state: str
    job_version: JobVersionName = Field(alias="jobVersion")
    started_at: datetime | None = Field(alias="startedAt")
    ended_at: datetime | None = Field(alias="endedAt")
    duration_ms: int = Field(alias="durationMs")
    args: dict[str, Any] = Field(default_factory=dict)
    facets: dict[str, Any] = Field(default_factory=dict)


class JobModel(ApiModel):
    id: NamespaceName
    type: str
    name: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    inputs: list[NamespaceName] = Field(default_factory=list)
    outputs: list[NamespaceName] = Field(default_factory=list)
    namespace: str
    location: str
    description: str
    simple_name: str = Field(alias="simpleName")
    latest_run: RunModel | None = Field(alias="latestRun")
    latest_runs: list[RunModel] = Field(default_factory=list, alias="latestRuns")
    tags: list[Any] = Field(default_factory=list)
    parent_job_name: str | None = Field(default=None, alias="parentJobName")
    parent_job_uuid: str | None = Field(default=None, alias="parentJobUuid")


class DatasetModel(ApiModel):
    id: NamespaceName
    type: str
    asset_kind: str = Field(default="DATASET", alias="assetKind")
    name: str
    physical_name: str = Field(alias="physicalName")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    namespace: str
    source_name: str = Field(alias="sourceName")
    fields: list[FieldModel] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    last_modified_at: datetime = Field(alias="lastModifiedAt")
    description: str
    facets: dict[str, Any] = Field(default_factory=dict)
    deleted: bool
    column_lineage: Any | None = Field(default=None, alias="columnLineage")


class DatasetVersionModel(ApiModel):
    id: VersionedNamespaceName
    type: str
    asset_kind: str = Field(default="DATASET", alias="assetKind")
    created_by_run: RunModel | None = Field(alias="createdByRun")
    name: str
    physical_name: str = Field(alias="physicalName")
    created_at: datetime = Field(alias="createdAt")
    version: str
    storage_uri: str | None = Field(default=None, alias="storageUri")
    namespace: str
    source_name: str = Field(alias="sourceName")
    fields: list[FieldModel] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    last_modified_at: datetime = Field(alias="lastModifiedAt")
    description: str
    lifecycle_state: str = Field(alias="lifecycleState")
    facets: dict[str, Any] = Field(default_factory=dict)


class RunFacetsModel(ApiModel):
    run_id: str = Field(alias="runId")
    facets: dict[str, Any] = Field(default_factory=dict)


class TagsResponse(ApiModel):
    tags: list[TagModel] = Field(default_factory=list)


class NamespacesResponse(ApiModel):
    namespaces: list[NamespaceModel] = Field(default_factory=list)


class JobsResponse(ApiModel):
    jobs: list[JobModel] = Field(default_factory=list)
    total_count: int = Field(alias="totalCount")


class RunsResponse(ApiModel):
    runs: list[RunModel] = Field(default_factory=list)
    total_count: int = Field(alias="totalCount")


class DatasetsResponse(ApiModel):
    datasets: list[DatasetModel] = Field(default_factory=list)
    total_count: int = Field(alias="totalCount")


class DatasetVersionsResponse(ApiModel):
    versions: list[DatasetVersionModel] = Field(default_factory=list)
    total_count: int = Field(alias="totalCount")


NodeType = Literal["JOB", "DATASET"]


class Edge(ApiModel):
    origin: str
    destination: str


class Node(ApiModel):
    id: str
    type: NodeType
    data: dict[str, Any]
    in_edges: list[Edge] = Field(default_factory=list, alias="inEdges")
    out_edges: list[Edge] = Field(default_factory=list, alias="outEdges")


class LineageResponse(ApiModel):
    graph: list[Node]


class IngestionResponse(ApiModel):
    status: IngestionStatus = IngestionStatus.ACCEPTED
    projected: bool
