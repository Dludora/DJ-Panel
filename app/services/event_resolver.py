from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from app.models.protocols.openlineage import (
    DatasetEvent,
    JobEvent,
    OpenLineageEvent,
    RunEvent,
)


class EventSchemaSuffix(str, Enum):
    RUN_EVENT = "/RunEvent"
    DATASET_EVENT = "/DatasetEvent"
    JOB_EVENT = "/JobEvent"


SCHEMA_SUFFIX_TO_MODEL = {
    EventSchemaSuffix.RUN_EVENT: RunEvent,
    EventSchemaSuffix.DATASET_EVENT: DatasetEvent,
    EventSchemaSuffix.JOB_EVENT: JobEvent,
}


def _schema_event_model(schema_url: str | None) -> type[OpenLineageEvent] | None:
    if not schema_url:
        return None

    last_slash = schema_url.rfind("/")
    if last_slash < 0:
        return None

    suffix = schema_url[last_slash:]
    for schema_suffix, event_model in SCHEMA_SUFFIX_TO_MODEL.items():
        if suffix == schema_suffix.value:
            return event_model

    return None


def resolve_event_model(payload: Mapping[str, Any]) -> type[OpenLineageEvent]:
    schema_model = _schema_event_model(payload.get("schemaURL"))
    if schema_model is not None:
        return schema_model

    if isinstance(payload.get("run"), Mapping):
        return RunEvent
    if isinstance(payload.get("dataset"), Mapping):
        return DatasetEvent
    if isinstance(payload.get("job"), Mapping):
        return JobEvent

    return RunEvent


def parse_event(payload: Mapping[str, Any]) -> OpenLineageEvent:
    event_model = resolve_event_model(payload)
    return event_model.model_validate(payload)
