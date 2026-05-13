from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import httpx

from dj_panel.app.config import get_settings
from dj_panel.app.execution.definitions import (
    ExecutionKind,
    WorkerType,
    worker_capabilities,
    worker_labels,
)
from dj_panel.app.models.api import (
    TaskArtifactCreateRequest,
    TaskClaimPayload,
    TaskClaimRequest,
    TaskClaimResponse,
    TaskTransitionRequest,
    WorkerHeartbeatRequest,
    WorkerRegisterRequest,
)
from dj_panel.app.models.constant import TaskKind


def client(base_url: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=get_settings().http_timeout_seconds,
    )


def register_dj_worker(
    http: httpx.Client,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    dj_bin: str,
    workdir: Path,
    task_kind: TaskKind,
) -> None:
    payload = WorkerRegisterRequest(
        workerId=worker_id,
        displayName=display_name,
        labels=worker_labels(
            host_name=os.uname().nodename, worker_type=WorkerType.DATAJUICER
        ),
        capabilities=worker_capabilities(
            execution_kind=ExecutionKind.DATAJUICER,
            task_kind=task_kind,
            workdir=workdir,
            dj_bin=dj_bin,
        ),
        maxConcurrency=1,
    )
    http.post(
        f"/api/v1/workspaces/{workspace}/workers/register",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()


def heartbeat_dj_worker(
    http: httpx.Client,
    worker_id: str,
    *,
    dj_bin: str,
    workdir: Path,
    task_kind: TaskKind,
) -> None:
    payload = WorkerHeartbeatRequest(
        status="ACTIVE",
        labels=worker_labels(
            host_name=os.uname().nodename, worker_type=WorkerType.DATAJUICER
        ),
        capabilities=worker_capabilities(
            execution_kind=ExecutionKind.DATAJUICER,
            task_kind=task_kind,
            workdir=workdir,
            dj_bin=dj_bin,
        ),
    )
    http.post(
        f"/api/v1/workers/{worker_id}/heartbeat",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()


def register_command_worker(
    http: httpx.Client,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    worker_type: WorkerType,
    task_kind: TaskKind,
    workdir: Path,
) -> None:
    payload = WorkerRegisterRequest(
        workerId=worker_id,
        displayName=display_name,
        labels=worker_labels(host_name=os.uname().nodename, worker_type=worker_type),
        capabilities=worker_capabilities(
            execution_kind=ExecutionKind.COMMAND,
            task_kind=task_kind,
            workdir=workdir,
        ),
        maxConcurrency=1,
    )
    http.post(
        f"/api/v1/workspaces/{workspace}/workers/register",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()


def heartbeat_command_worker(
    http: httpx.Client,
    worker_id: str,
    *,
    worker_type: WorkerType,
    task_kind: TaskKind,
    workdir: Path,
) -> None:
    payload = WorkerHeartbeatRequest(
        status="ACTIVE",
        labels=worker_labels(host_name=os.uname().nodename, worker_type=worker_type),
        capabilities=worker_capabilities(
            execution_kind=ExecutionKind.COMMAND,
            task_kind=task_kind,
            workdir=workdir,
        ),
    )
    http.post(
        f"/api/v1/workers/{worker_id}/heartbeat",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()


def claim_task(
    http: httpx.Client, workspace: str, worker_id: str, task_kinds: list[TaskKind]
) -> Optional[TaskClaimPayload]:
    payload = TaskClaimRequest(workerId=worker_id, supportedTaskKinds=task_kinds)
    response = http.post(
        f"/api/v1/workspaces/{workspace}/tasks/claim",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    )
    response.raise_for_status()
    parsed = TaskClaimResponse.model_validate(response.json())
    return parsed.task if parsed.claimed else None


def post_transition(
    http: httpx.Client, task_id: str, suffix: str, body: dict[str, Any]
) -> None:
    payload = TaskTransitionRequest.model_validate(body)
    http.post(
        f"/api/v1/tasks/{task_id}/{suffix}",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()


def post_artifact(
    http: httpx.Client,
    attempt_id: str,
    *,
    kind: str,
    name: str,
    uri: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = TaskArtifactCreateRequest(
        kind=kind,
        name=name,
        uri=uri,
        metadata=metadata or {},
    )
    http.post(
        f"/api/v1/task-attempts/{attempt_id}/artifacts",
        json=payload.model_dump(by_alias=True, exclude_none=True),
    ).raise_for_status()
