from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from app.db.schema import (
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
)
from app.models.lineage_enums import DatasetLifecycleState, JobVersionIOType
from app.models.openlineage import RunEventType
from app.services.event_resolver import parse_event
from app.services.ingestion import IngestionService

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
    return IngestionService(engine)


def test_start_then_complete_updates_run_and_creates_job_version_and_dataset_version(ingestion_service, engine) -> None:
    start_payload = load_event('run_start.json')
    complete_payload = load_event('run_complete.json')

    start_event = parse_event(start_payload)
    complete_event = parse_event(complete_payload)

    start_result = ingestion_service.ingest(start_event, start_payload)
    assert start_result.projected is True

    with engine.begin() as conn:
        run_row = conn.execute(select(runs)).mappings().one()
        assert run_row['run_id'] == 'run-001'
        assert run_row['state'] == 'START'
        assert run_row['started_at'] is not None
        assert run_row['ended_at'] is None
        assert run_row['job_version_id'] is None
        assert conn.execute(select(job_versions)).mappings().all() == []
        assert conn.execute(select(dataset_versions)).mappings().all() == []

    complete_result = ingestion_service.ingest(complete_event, complete_payload)
    assert complete_result.projected is True

    with engine.begin() as conn:
        run_row = conn.execute(select(runs)).mappings().one()
        job_row = conn.execute(select(jobs)).mappings().one()
        versions = conn.execute(select(job_versions)).mappings().all()
        mappings = conn.execute(select(job_version_io_mapping)).mappings().all()
        dataset_version_rows = conn.execute(select(dataset_versions)).mappings().all()

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
        assert len(dataset_version_rows) == 1
        assert dataset_version_rows[0]['lifecycle_state'] == DatasetLifecycleState.ACTIVE.value


def test_facets_namespaces_and_dataset_versions_are_projected(ingestion_service, engine) -> None:
    complete_payload = load_event('run_complete.json')
    complete_event = parse_event(complete_payload)
    ingestion_service.ingest(complete_event, complete_payload)

    with engine.begin() as conn:
        run_facet_rows = conn.execute(select(run_facets.c.facet_name, run_facets.c.payload)).all()
        job_facet_rows = conn.execute(select(job_facets.c.facet_name, job_facets.c.payload)).all()
        dataset_rows = conn.execute(select(datasets)).mappings().all()
        dataset_facet_rows = conn.execute(
            select(dataset_facets.c.dataset_id, dataset_facets.c.facet_name, dataset_facets.c.payload)
        ).all()
        namespace_rows = conn.execute(select(namespaces.c.name)).all()
        dataset_version_row = conn.execute(select(dataset_versions)).mappings().one()

    run_facets_by_name = {name: payload for name, payload in run_facet_rows}
    job_facets_by_name = {name: payload for name, payload in job_facet_rows}

    assert 'datajuicer_run' in run_facets_by_name
    assert run_facets_by_name['datajuicer_run']['phase'] == 'complete'
    assert 'execution_parameters' in run_facets_by_name
    assert run_facets_by_name['execution_parameters']['parameters']['lr'] == 0.001

    assert 'datajuicer' in job_facets_by_name
    assert job_facets_by_name['datajuicer']['recipe'] == 'train_recipe'
    assert 'jobType' in job_facets_by_name
    assert job_facets_by_name['jobType']['processingType'] == 'BATCH'

    dataset_by_name = {row['name']: row['id'] for row in dataset_rows}
    dataset_facets_grouped: dict[tuple[str, str], dict] = {
        (dataset_id, facet_name): payload for dataset_id, facet_name, payload in dataset_facet_rows
    }

    training_dataset_id = dataset_by_name['training_dataset']
    model_dataset_id = dataset_by_name['model_artifact']
    model_dataset_row = next(row for row in dataset_rows if row['name'] == 'model_artifact')

    assert dataset_facets_grouped[(training_dataset_id, 'schema')]['fields'][1]['name'] == 'feature'
    assert dataset_facets_grouped[(training_dataset_id, '_input_facets')]['dataQuality']['rowCount'] == 100
    assert dataset_facets_grouped[(model_dataset_id, 'mlflow_model')]['registry_stage'] == 'staging'
    assert dataset_facets_grouped[(model_dataset_id, '_output_facets')]['outputStatistics']['rowCount'] == 1
    assert model_dataset_row['asset_kind'] == 'MODEL'
    assert {row[0] for row in namespace_rows} == {'demo'}
    assert dataset_version_row['fields'][0]['name'] == 'artifact_path'


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
        job_facet_rows = conn.execute(select(job_facets.c.facet_name, job_facets.c.payload)).all()
        dataset_facet_rows = conn.execute(select(dataset_facets.c.dataset_id, dataset_facets.c.facet_name, dataset_facets.c.payload)).all()

    assert run_rows == []
    assert {row['name'] for row in dataset_rows} == {
        'feature_store_snapshot',
        'registered_model',
    }
    assert job_rows[0]['name'] == 'declared_train_model'

    job_facets_by_name = {name: payload for name, payload in job_facet_rows}
    assert job_facets_by_name['jobType']['processingType'] == 'BATCH'

    dataset_by_name = {row['name']: row['id'] for row in dataset_rows}
    grouped_dataset_facets = {
        (dataset_id, facet_name): payload for dataset_id, facet_name, payload in dataset_facet_rows
    }
    assert grouped_dataset_facets[(dataset_by_name['feature_store_snapshot'], 'schema')]['fields'][0]['name'] == 'id'
    assert grouped_dataset_facets[(dataset_by_name['registered_model'], 'mlflow_model')]['registry_stage'] == 'production'
