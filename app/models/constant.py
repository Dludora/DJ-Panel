from __future__ import annotations

from enum import Enum

from app.models.protocols.openlineage import RunEventType


class WorkerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"


class RunSubmissionStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunSubmissionKind(str, Enum):
    PROCESSING_PIPELINE = "processing_pipeline"
    TRAINING = "training"
    EVALUATION = "evaluation"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskKind(str, Enum):
    DJ_RECIPE = "dj_recipe"
    TRAINING = "training"
    EVALUATION = "evaluation"
    GENERIC_COMMAND = "generic_command"


class TaskAttemptStatus(str, Enum):
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ArtifactKind(str, Enum):
    FILE = "FILE"
    DATASET = "DATASET"
    MODEL = "MODEL"
    METRICS = "METRICS"
    LOG = "LOG"


class JobVersionIOType(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class DatasetLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"


class JobProcessingType(str, Enum):
    BATCH = "BATCH"
    STREAM = "STREAM"
    SERVICE = "SERVICE"


class WebRunState(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


RUN_EVENT_TO_WEB_RUN_STATE = {
    RunEventType.START: WebRunState.RUNNING,
    RunEventType.RUNNING: WebRunState.RUNNING,
    RunEventType.COMPLETE: WebRunState.COMPLETED,
    RunEventType.FAIL: WebRunState.FAILED,
    RunEventType.ABORT: WebRunState.ABORTED,
}
