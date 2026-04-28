from __future__ import annotations

from enum import Enum


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


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


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


class LogStream(str, Enum):
    STDOUT = "STDOUT"
    STDERR = "STDERR"
    EVENT = "EVENT"
