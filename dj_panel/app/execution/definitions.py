from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dj_panel.app.config import get_settings
from dj_panel.app.models.constant import TaskKind


class WorkerMode(str, Enum):
    DJ = "dj"
    TRAIN = "train"
    EVAL = "eval"


class WorkerType(str, Enum):
    DATAJUICER = "datajuicer"
    TRAIN = "train"
    EVAL = "eval"


class ExecutionKind(str, Enum):
    DATAJUICER = "datajuicer"
    COMMAND = "command"


_settings = get_settings()
DEFAULT_DJ_BIN = _settings.dj_bin
DEFAULT_DJ_CONFIG_ARG = _settings.dj_config_arg
DEFAULT_DJ_COMMAND = _settings.default_dj_command


@dataclass(frozen=True)
class WorkerProfile:
    mode: WorkerMode
    worker_type: WorkerType
    execution_kind: ExecutionKind
    task_kind: TaskKind


DJ_WORKER_PROFILE = WorkerProfile(
    mode=WorkerMode.DJ,
    worker_type=WorkerType.DATAJUICER,
    execution_kind=ExecutionKind.DATAJUICER,
    task_kind=TaskKind.DJ_RECIPE,
)

TRAIN_WORKER_PROFILE = WorkerProfile(
    mode=WorkerMode.TRAIN,
    worker_type=WorkerType.TRAIN,
    execution_kind=ExecutionKind.COMMAND,
    task_kind=TaskKind.TRAINING,
)

EVAL_WORKER_PROFILE = WorkerProfile(
    mode=WorkerMode.EVAL,
    worker_type=WorkerType.EVAL,
    execution_kind=ExecutionKind.COMMAND,
    task_kind=TaskKind.EVALUATION,
)


def worker_profile_for_mode(mode: WorkerMode) -> WorkerProfile:
    if mode == WorkerMode.DJ:
        return DJ_WORKER_PROFILE
    if mode == WorkerMode.TRAIN:
        return TRAIN_WORKER_PROFILE
    return EVAL_WORKER_PROFILE


def worker_labels(*, host_name: str, worker_type: WorkerType) -> dict[str, str]:
    return {
        "host": host_name,
        "workerType": worker_type.value,
    }


def worker_capabilities(
    *,
    execution_kind: ExecutionKind,
    task_kind: TaskKind,
    workdir: Path,
    dj_bin: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "execution": execution_kind.value,
        "taskKinds": [task_kind.value],
        "workdir": str(workdir),
    }
    if dj_bin:
        payload["djBin"] = dj_bin
    return payload
