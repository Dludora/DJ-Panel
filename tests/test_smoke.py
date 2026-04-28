from app.models.schemas.openlineage import DatasetEvent, JobEvent, RunEvent
from app.services.event_resolver import parse_event, resolve_event_model


def test_default_run_event_is_selected_from_shape() -> None:
    payload = {
        "eventType": "COMPLETE",
        "job": {"namespace": "demo", "name": "job"},
        "run": {"runId": "run-1"},
    }
    event = parse_event(payload)
    assert isinstance(event, RunEvent)
    assert resolve_event_model(payload) is RunEvent


def test_job_event_is_selected_from_schema_url() -> None:
    payload = {
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/JobEvent",
        "job": {"namespace": "demo", "name": "job"},
    }
    event = parse_event(payload)
    assert isinstance(event, JobEvent)
    assert resolve_event_model(payload) is JobEvent


def test_dataset_event_is_selected_from_schema_url() -> None:
    payload = {
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/DatasetEvent",
        "dataset": {"namespace": "demo", "name": "dataset"},
    }
    event = parse_event(payload)
    assert isinstance(event, DatasetEvent)
    assert resolve_event_model(payload) is DatasetEvent


def test_schema_root_falls_back_to_run_event_shape() -> None:
    payload = {
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
        "eventType": "START",
        "job": {"namespace": "demo", "name": "job"},
        "run": {"runId": "run-1"},
    }
    event = parse_event(payload)
    assert isinstance(event, RunEvent)
    assert resolve_event_model(payload) is RunEvent
