from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunRef(BaseModel):
    run_id: str = Field(alias="runId")
    facets: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class JobRef(BaseModel):
    namespace: str
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)


class DatasetRef(BaseModel):
    namespace: str
    name: str
    facets: dict[str, Any] = Field(default_factory=dict)
    input_facets: dict[str, Any] = Field(default_factory=dict, alias="inputFacets")
    output_facets: dict[str, Any] = Field(default_factory=dict, alias="outputFacets")

    model_config = ConfigDict(populate_by_name=True)


class BaseEvent(BaseModel):
    schema_url: str | None = Field(default=None, alias="schemaURL")
    event_time: datetime | None = Field(default=None, alias="eventTime")
    producer: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class RunEventType(str, Enum):
    START = "START"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    ABORT = "ABORT"
    FAIL = "FAIL"
    OTHER = "OTHER"


class RunEvent(BaseEvent):
    event_type: RunEventType | None = Field(default=None, alias="eventType")
    run: RunRef
    job: JobRef
    inputs: list[DatasetRef] = Field(default_factory=list)
    outputs: list[DatasetRef] = Field(default_factory=list)


class JobEvent(BaseEvent):
    job: JobRef
    inputs: list[DatasetRef] = Field(default_factory=list)
    outputs: list[DatasetRef] = Field(default_factory=list)


class DatasetEvent(BaseEvent):
    dataset: DatasetRef


OpenLineageEvent = RunEvent | DatasetEvent | JobEvent
