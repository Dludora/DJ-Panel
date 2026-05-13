from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from dj_panel.app.db.schema import (
    dataset_facets,
    dataset_versions,
    datasets,
    job_facets,
    job_version_io_mapping,
    job_versions,
    jobs,
    metadata,
    namespaces,
    run_facets,
    runs,
    tasks,
    task_attempts,
    execution_links,
)
from dj_panel.app.models.constant import DatasetLifecycleState, JobVersionIOType
from dj_panel.app.models.protocols.openlineage import RunEventType
from dj_panel.app.utils.openlineage_utils import parse_event
from dj_panel.app.services.lineage import LineageService
from dj_panel.app.utils.common_utils import new_id, utc_now

FIXTURES = Path(__file__).parent / 'fixtures'


def load_event(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture()
def engine():
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        future=True,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)


@pytest.fixture()
def ingestion_service(engine):
    return LineageService(engine)


def test_start_then_complete_updates_run_and_creates_job_version_and_dataset_version(ingestion_service, engine) -> None:
    start_payload = load_event('run_start.json')
    complete_payload = load_event('run_complete.json')

    start_event = parse_event(start_payload)
    complete_event = parse_event(complete_payload)

    start_result = ingestion_service.ingest(start_event, start_payload)
    assert start_result.projected is True

    with engine.begin() as conn:
        run_row = conn.execute(select(runs)).mappings().one()
        dataset_rows = conn.execute(select(datasets)).mappings().all()
        dataset_version_rows = conn.execute(select(dataset_versions)).mappings().all()
        assert run_row['run_id'] == 'run-001'
        assert run_row['state'] == 'START'
        assert run_row['started_at'] is not None
        assert run_row['ended_at'] is None
        assert run_row['job_version_id'] is None
        assert conn.execute(select(job_versions)).mappings().all() == []
        assert len(dataset_version_rows) == 1
        training_dataset = next(row for row in dataset_rows if row["name"] == "training_dataset")
        model_dataset = next(row for row in dataset_rows if row["name"] == "model_artifact")
        assert training_dataset["current_version_id"] is not None
        assert model_dataset["current_version_id"] is None

    complete_result = ingestion_service.ingest(complete_event, complete_payload)
    assert complete_result.projected is True

    with engine.begin() as conn:
        run_row = conn.execute(select(runs)).mappings().one()
        job_row = conn.execute(select(jobs)).mappings().one()
        versions = conn.execute(select(job_versions)).mappings().all()
        mappings = conn.execute(select(job_version_io_mapping)).mappings().all()
        dataset_version_rows = conn.execute(select(dataset_versions)).mappings().all()
        dataset_rows = conn.execute(select(datasets)).mappings().all()

        assert run_row['state'] == RunEventType.COMPLETE.value
        assert run_row['job_version_id'] is not None
        assert run_row['ended_at'] is not None
        assert len(versions) == 1
        assert versions[0]['is_current'] is True
        assert job_row['current_job_version_id'] == versions[0]['id'] == run_row['job_version_id']
        assert sorted(row['io_type'] for row in mappings) == [
            JobVersionIOType.INPUT.value,
            JobVersionIOType.OUTPUT.value,
        ]
        assert len(dataset_version_rows) == 2
        output_versions = [
            row for row in dataset_version_rows if row["created_by_run_id"] == run_row["id"]
        ]
        assert len(output_versions) == 1
        assert all(
            row['lifecycle_state'] == DatasetLifecycleState.ACTIVE.value
            for row in dataset_version_rows
        )
        model_dataset = next(row for row in dataset_rows if row["name"] == "model_artifact")
        assert model_dataset["current_version_id"] is not None
        assert any(row["id"] == model_dataset["current_version_id"] for row in output_versions)


def test_facets_namespaces_and_dataset_versions_are_projected(ingestion_service, engine) -> None:
    complete_payload = load_event('run_complete.json')
    complete_event = parse_event(complete_payload)
    ingestion_service.ingest(complete_event, complete_payload)

    with engine.begin() as conn:
        run_facet_rows = conn.execute(select(run_facets.c.facet_name, run_facets.c.payload)).all()
        job_facet_rows = conn.execute(
            select(
                job_facets.c.facet_name,
                job_facets.c.payload,
                job_facets.c.job_version_id,
                job_facets.c.run_id,
            )
        ).all()
        dataset_rows = conn.execute(select(datasets)).mappings().all()
        dataset_facet_rows = conn.execute(
            select(
                dataset_facets.c.asset_id,
                dataset_facets.c.facet_name,
                dataset_facets.c.payload,
                dataset_facets.c.asset_version_id,
                dataset_facets.c.run_id,
            )
        ).all()
        namespace_rows = conn.execute(select(namespaces.c.name)).all()
        dataset_version_rows = conn.execute(select(dataset_versions)).mappings().all()

    run_facets_by_name = {name: payload for name, payload in run_facet_rows}
    job_facets_by_name = {name: payload for name, payload, _, _ in job_facet_rows}

    assert 'datajuicer_run' in run_facets_by_name
    assert run_facets_by_name['datajuicer_run']['phase'] == 'complete'
    assert 'execution_parameters' in run_facets_by_name
    assert run_facets_by_name['execution_parameters']['parameters']['lr'] == 0.001

    assert 'datajuicer' in job_facets_by_name
    assert job_facets_by_name['datajuicer']['recipe'] == 'train_recipe'
    assert 'jobType' in job_facets_by_name
    assert job_facets_by_name['jobType']['processingType'] == 'BATCH'
    assert any(job_version_id is not None for _, _, job_version_id, _ in job_facet_rows)
    assert any(run_id is not None for _, _, _, run_id in job_facet_rows)

    dataset_by_name = {row['name']: row['id'] for row in dataset_rows}
    dataset_facets_grouped: dict[tuple[str, str], tuple[dict, str | None, str | None]] = {
        (dataset_id, facet_name): (payload, asset_version_id, run_id)
        for dataset_id, facet_name, payload, asset_version_id, run_id in dataset_facet_rows
    }

    training_dataset_id = dataset_by_name['training_dataset']
    model_dataset_id = dataset_by_name['model_artifact']
    model_dataset_row = next(row for row in dataset_rows if row['name'] == 'model_artifact')
    model_dataset_version_row = next(
        row for row in dataset_version_rows if row["created_by_run_id"] is not None
    )

    training_schema_payload, training_schema_version_id, training_schema_run_id = dataset_facets_grouped[(training_dataset_id, 'schema')]
    training_input_payload, training_input_version_id, training_input_run_id = dataset_facets_grouped[(training_dataset_id, '_input_facets')]
    model_mlflow_payload, model_mlflow_version_id, model_mlflow_run_id = dataset_facets_grouped[(model_dataset_id, 'mlflow_model')]
    model_output_payload, model_output_version_id, model_output_run_id = dataset_facets_grouped[(model_dataset_id, '_output_facets')]
    assert training_schema_payload['fields'][1]['name'] == 'feature'
    assert training_input_payload['dataQuality']['rowCount'] == 100
    assert model_mlflow_payload['registry_stage'] == 'staging'
    assert model_output_payload['outputStatistics']['rowCount'] == 1
    assert model_dataset_row['asset_kind'] == 'MODEL'
    assert model_dataset_row['current_version_id'] == model_dataset_version_row['id']
    assert training_schema_version_id is not None
    assert training_input_version_id is not None
    assert model_mlflow_version_id == model_dataset_version_row['id']
    assert model_output_version_id == model_dataset_version_row['id']
    assert training_schema_run_id is not None
    assert training_input_run_id is not None
    assert model_mlflow_run_id is not None
    assert model_output_run_id is not None
    assert {row[0] for row in namespace_rows} == {'demo'}
    assert model_dataset_version_row['fields'][0]['name'] == 'artifact_path'


def test_job_and_dataset_events_are_accepted_and_distinguished(ingestion_service, engine) -> None:
    dataset_payload = load_event('dataset_event.json')
    job_payload = load_event('job_event.json')

    dataset_result = ingestion_service.ingest(parse_event(dataset_payload), dataset_payload)
    job_result = ingestion_service.ingest(parse_event(job_payload), job_payload)

    assert dataset_result.projected is True
    assert job_result.projected is True

    with engine.begin() as conn:
        dataset_rows = conn.execute(select(datasets)).mappings().all()
        job_rows = conn.execute(select(jobs)).mappings().all()
        run_rows = conn.execute(select(runs)).mappings().all()
        job_version_rows = conn.execute(select(job_versions)).mappings().all()
        job_version_io_rows = conn.execute(select(job_version_io_mapping)).mappings().all()
        dataset_version_rows = conn.execute(select(dataset_versions)).mappings().all()
        job_facet_rows = conn.execute(
            select(
                job_facets.c.facet_name,
                job_facets.c.payload,
                job_facets.c.job_version_id,
                job_facets.c.run_id,
            )
        ).all()
        dataset_facet_rows = conn.execute(
            select(
                dataset_facets.c.asset_id,
                dataset_facets.c.facet_name,
                dataset_facets.c.payload,
                dataset_facets.c.asset_version_id,
                dataset_facets.c.run_id,
            )
        ).all()

    assert run_rows == []
    assert {row['name'] for row in dataset_rows} == {
        'feature_store_snapshot',
        'registered_model',
    }
    assert job_rows[0]['name'] == 'declared_train_model'
    assert job_rows[0]['current_job_version_id'] is not None
    assert len(job_version_rows) == 1
    assert job_version_rows[0]['id'] == job_rows[0]['current_job_version_id']
    assert sorted(row['io_type'] for row in job_version_io_rows) == [
        JobVersionIOType.INPUT.value,
        JobVersionIOType.OUTPUT.value,
    ]

    job_facets_by_name = {name: payload for name, payload, _, _ in job_facet_rows}
    assert job_facets_by_name['jobType']['processingType'] == 'BATCH'
    assert any(job_version_id is not None for _, _, job_version_id, _ in job_facet_rows)
    assert all(run_id is None for _, _, _, run_id in job_facet_rows)

    dataset_by_name = {row['name']: row['id'] for row in dataset_rows}
    grouped_dataset_facets = {
        (dataset_id, facet_name): (payload, asset_version_id, run_id)
        for dataset_id, facet_name, payload, asset_version_id, run_id in dataset_facet_rows
    }
    feature_payload, feature_version_id, feature_run_id = grouped_dataset_facets[(dataset_by_name['feature_store_snapshot'], 'schema')]
    model_payload, model_version_id, model_run_id = grouped_dataset_facets[(dataset_by_name['registered_model'], 'mlflow_model')]
    assert feature_payload['fields'][0]['name'] == 'id'
    assert model_payload['registry_stage'] == 'production'
    assert feature_version_id is not None
    assert model_version_id is not None
    assert feature_run_id is None
    assert model_run_id is None
    assert len(dataset_version_rows) == 2
    feature_store_snapshot = next(row for row in dataset_rows if row["name"] == "feature_store_snapshot")
    registered_model = next(row for row in dataset_rows if row["name"] == "registered_model")
    assert feature_store_snapshot["current_version_id"] is not None
    assert registered_model["current_version_id"] is not None


def test_pipeline_run_event_links_task_by_datajuicer_job_id(ingestion_service, engine) -> None:
    now = utc_now()
    task_id = new_id()
    attempt_id = new_id()
    submission_id = new_id()
    workspace_id = new_id()

    with engine.begin() as conn:
        conn.execute(
            tasks.insert().values(
                id=task_id,
                workspace_id=workspace_id,
                run_submission_id=submission_id,
                recipe_version_id=None,
                task_kind="dj_recipe",
                status="CLAIMED",
                attempt_count=1,
                current_attempt_id=attempt_id,
                command="dj-process --config recipe.yaml",
                script_path="/tmp/recipe.yaml",
                env_vars={},
                execution_spec={},
                timeout_seconds=3600,
                created_at=now,
            )
        )
        conn.execute(
            task_attempts.insert().values(
                id=attempt_id,
                task_id=task_id,
                worker_id="worker-1",
                attempt_number=1,
                status="CLAIMED",
                lease_token="lease-token",
                created_at=now,
                updated_at=now,
                last_heartbeat_at=now,
            )
        )

    payload = load_event("run_complete.json")
    payload["run"]["runId"] = "ol-run-task-link-1"
    payload["run"]["facets"]["datajuicer"] = {"jobId": task_id}
    ingestion_service.ingest(parse_event(payload), payload)

    with engine.begin() as conn:
        attempt_row = conn.execute(
            select(task_attempts).where(task_attempts.c.id == attempt_id)
        ).mappings().one()
        link_row = conn.execute(select(execution_links)).mappings().one()
        run_row = conn.execute(select(runs)).mappings().one()

    assert attempt_row["openlineage_run_id"] == "ol-run-task-link-1"
    assert link_row["task_id"] == task_id
    assert link_row["task_attempt_id"] == attempt_id
    assert link_row["run_submission_id"] == submission_id
    assert link_row["openlineage_run_id"] == "ol-run-task-link-1"
    assert run_row["run_id"] == "ol-run-task-link-1"
