from enum import Enum

from app.models.openlineage import RunEventType


class JobVersionIOType(str, Enum):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'


class DatasetLifecycleState(str, Enum):
    ACTIVE = 'ACTIVE'


class JobProcessingType(str, Enum):
    BATCH = 'BATCH'
    STREAM = 'STREAM'
    SERVICE = 'SERVICE'


class WebRunState(str, Enum):
    NEW = 'NEW'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    ABORTED = 'ABORTED'


RUN_EVENT_TO_WEB_RUN_STATE = {
    RunEventType.START: WebRunState.RUNNING,
    RunEventType.RUNNING: WebRunState.RUNNING,
    RunEventType.COMPLETE: WebRunState.COMPLETED,
    RunEventType.FAIL: WebRunState.FAILED,
    RunEventType.ABORT: WebRunState.ABORTED,
}
