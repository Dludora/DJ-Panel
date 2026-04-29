from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional


def _value(mapping: Mapping[str, Any], key: str) -> Any:
    return mapping[key]


@dataclass(frozen=True)
class WorkspaceRow:
    id: str
    slug: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "WorkspaceRow":
        return cls(
            id=_value(mapping, "id"),
            slug=_value(mapping, "slug"),
            name=_value(mapping, "name"),
            description=_value(mapping, "description"),
            created_at=_value(mapping, "created_at"),
            updated_at=_value(mapping, "updated_at"),
        )


@dataclass(frozen=True)
class WorkspaceMemberRow:
    id: str
    workspace_id: str
    user_name: str
    role: str
    created_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "WorkspaceMemberRow":
        return cls(
            id=_value(mapping, "id"),
            workspace_id=_value(mapping, "workspace_id"),
            user_name=_value(mapping, "user_name"),
            role=_value(mapping, "role"),
            created_at=_value(mapping, "created_at"),
        )


@dataclass(frozen=True)
class RecipeRow:
    id: str
    workspace_id: str
    name: str
    description: str
    owner_name: str
    current_version_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "RecipeRow":
        return cls(
            id=_value(mapping, "id"),
            workspace_id=_value(mapping, "workspace_id"),
            name=_value(mapping, "name"),
            description=_value(mapping, "description"),
            owner_name=_value(mapping, "owner_name"),
            current_version_id=mapping.get("current_version_id"),
            created_at=_value(mapping, "created_at"),
            updated_at=_value(mapping, "updated_at"),
        )


@dataclass(frozen=True)
class RecipeVersionRow:
    id: str
    recipe_id: str
    version_number: int
    recipe_body: dict[str, Any]
    command: str
    script_path: str
    parameter_schema: dict[str, Any]
    env_template: dict[str, Any]
    execution_spec: dict[str, Any]
    timeout_seconds: int
    created_by: str
    created_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "RecipeVersionRow":
        return cls(
            id=_value(mapping, "id"),
            recipe_id=_value(mapping, "recipe_id"),
            version_number=_value(mapping, "version_number"),
            recipe_body=_value(mapping, "recipe_body") or {},
            command=_value(mapping, "command"),
            script_path=_value(mapping, "script_path"),
            parameter_schema=_value(mapping, "parameter_schema") or {},
            env_template=_value(mapping, "env_template") or {},
            execution_spec=_value(mapping, "execution_spec") or {},
            timeout_seconds=_value(mapping, "timeout_seconds"),
            created_by=_value(mapping, "created_by"),
            created_at=_value(mapping, "created_at"),
        )


@dataclass(frozen=True)
class RunSubmissionRow:
    id: str
    workspace_id: str
    recipe_id: Optional[str]
    recipe_version_id: Optional[str]
    name: Optional[str]
    requested_by: str
    submission_kind: str
    status: str
    parameters: dict[str, Any]
    spec: dict[str, Any]
    root_lineage_node_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    failure_reason: Optional[str]

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "RunSubmissionRow":
        return cls(
            id=_value(mapping, "id"),
            workspace_id=_value(mapping, "workspace_id"),
            recipe_id=mapping.get("recipe_id"),
            recipe_version_id=mapping.get("recipe_version_id"),
            name=mapping.get("name"),
            requested_by=_value(mapping, "requested_by"),
            submission_kind=mapping.get("submission_kind", "processing_pipeline"),
            status=_value(mapping, "status"),
            parameters=_value(mapping, "parameters") or {},
            spec=_value(mapping, "spec") or {},
            root_lineage_node_id=mapping.get("root_lineage_node_id"),
            created_at=_value(mapping, "created_at"),
            started_at=mapping.get("started_at"),
            ended_at=mapping.get("ended_at"),
            failure_reason=mapping.get("failure_reason"),
        )


@dataclass(frozen=True)
class WorkerRow:
    id: str
    workspace_id: str
    display_name: str
    status: str
    labels: dict[str, Any]
    capabilities: dict[str, Any]
    max_concurrency: int
    last_heartbeat_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "WorkerRow":
        return cls(
            id=_value(mapping, "id"),
            workspace_id=_value(mapping, "workspace_id"),
            display_name=_value(mapping, "display_name"),
            status=_value(mapping, "status"),
            labels=_value(mapping, "labels") or {},
            capabilities=_value(mapping, "capabilities") or {},
            max_concurrency=_value(mapping, "max_concurrency"),
            last_heartbeat_at=mapping.get("last_heartbeat_at"),
            created_at=_value(mapping, "created_at"),
            updated_at=_value(mapping, "updated_at"),
        )


@dataclass(frozen=True)
class TaskRow:
    id: str
    workspace_id: str
    run_submission_id: str
    recipe_version_id: Optional[str]
    task_kind: str
    status: str
    assigned_worker_id: Optional[str]
    current_attempt_id: Optional[str]
    lease_token: Optional[str]
    lease_expires_at: Optional[datetime]
    attempt_count: int
    command: str
    script_path: str
    env_vars: dict[str, Any]
    execution_spec: dict[str, Any]
    timeout_seconds: int
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    failure_reason: Optional[str]

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "TaskRow":
        return cls(
            id=_value(mapping, "id"),
            workspace_id=_value(mapping, "workspace_id"),
            run_submission_id=_value(mapping, "run_submission_id"),
            recipe_version_id=mapping.get("recipe_version_id"),
            task_kind=mapping.get("task_kind", "generic_command"),
            status=_value(mapping, "status"),
            assigned_worker_id=mapping.get("assigned_worker_id"),
            current_attempt_id=mapping.get("current_attempt_id"),
            lease_token=mapping.get("lease_token"),
            lease_expires_at=mapping.get("lease_expires_at"),
            attempt_count=_value(mapping, "attempt_count"),
            command=_value(mapping, "command"),
            script_path=_value(mapping, "script_path"),
            env_vars=_value(mapping, "env_vars") or {},
            execution_spec=_value(mapping, "execution_spec") or {},
            timeout_seconds=_value(mapping, "timeout_seconds"),
            created_at=_value(mapping, "created_at"),
            started_at=mapping.get("started_at"),
            ended_at=mapping.get("ended_at"),
            failure_reason=mapping.get("failure_reason"),
        )


@dataclass(frozen=True)
class TaskAttemptRow:
    id: str
    task_id: str
    worker_id: str
    attempt_number: int
    status: str
    lease_token: str
    openlineage_run_id: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    last_heartbeat_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "TaskAttemptRow":
        return cls(
            id=_value(mapping, "id"),
            task_id=_value(mapping, "task_id"),
            worker_id=_value(mapping, "worker_id"),
            attempt_number=_value(mapping, "attempt_number"),
            status=_value(mapping, "status"),
            lease_token=_value(mapping, "lease_token"),
            openlineage_run_id=mapping.get("openlineage_run_id"),
            started_at=mapping.get("started_at"),
            ended_at=mapping.get("ended_at"),
            last_heartbeat_at=mapping.get("last_heartbeat_at"),
            failure_reason=mapping.get("failure_reason"),
            created_at=_value(mapping, "created_at"),
            updated_at=_value(mapping, "updated_at"),
        )
