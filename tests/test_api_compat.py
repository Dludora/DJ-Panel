from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.routes.lineage import get_ingestion_service, get_lineage_query_service
from app.api.routes.metadata import get_metadata_service
from app.db.session import get_engine
from app.db.schema import metadata
from app.main import app
from app.models.api import IngestionStatus
from app.services.ingestion import IngestionService
from app.services.lineage_query import LineageQueryService
from app.services.metadata import MetadataService

FIXTURES = Path(__file__).parent / 'fixtures'


def load_event(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture()
def client():
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        future=True,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(engine)
    app.dependency_overrides[get_lineage_query_service] = lambda: LineageQueryService(engine)
    app.dependency_overrides[get_metadata_service] = lambda: MetadataService(engine)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        metadata.drop_all(engine)


def test_lineage_and_metadata_endpoints_are_marquez_friendly(client: TestClient) -> None:
    client.post('/api/v1/lineage', json=load_event('run_start.json')).raise_for_status()
    client.post('/api/v1/lineage', json=load_event('run_complete.json')).raise_for_status()

    lineage = client.get('/api/v1/lineage', params={'nodeId': 'job:demo:train_model', 'depth': 1})
    assert lineage.status_code == 200
    graph = lineage.json()['graph']
    job_node = next(node for node in graph if node['id'] == 'job:demo:train_model')
    dataset_node = next(node for node in graph if node['id'] == 'dataset:demo:model_artifact')

    assert job_node['type'] == 'JOB'
    assert job_node['data']['latestRun']['state'] == 'COMPLETED'
    assert job_node['data']['inputs'][0] == {'namespace': 'demo', 'name': 'training_dataset'}
    assert dataset_node['type'] == 'DATASET'
    assert dataset_node['data']['fields'][0]['name'] == 'artifact_path'
    assert dataset_node['data']['facets']['mlflow_model']['registry_stage'] == 'staging'

    jobs = client.get('/api/v1/jobs', params={'limit': 25, 'offset': 0})
    assert jobs.status_code == 200
    jobs_payload = jobs.json()
    assert jobs_payload['totalCount'] == 1
    assert jobs_payload['jobs'][0]['name'] == 'train_model'

    jobs_by_state = client.get('/api/v1/jobs', params={'limit': 25, 'offset': 0, 'lastRunStates': 'COMPLETED'})
    assert jobs_by_state.status_code == 200
    assert jobs_by_state.json()['totalCount'] == 1

    jobs_by_namespace = client.get('/api/v1/namespaces/demo/jobs', params={'limit': 25, 'offset': 0})
    assert jobs_by_namespace.status_code == 200
    assert jobs_by_namespace.json()['jobs'][0]['namespace'] == 'demo'

    job = client.get('/api/v1/namespaces/demo/jobs/train_model')
    assert job.status_code == 200
    job_payload = job.json()
    assert job_payload['type'] == 'BATCH'
    assert job_payload['latestRuns'][0]['state'] == 'COMPLETED'

    runs = client.get('/api/v1/namespaces/demo/jobs/train_model/runs', params={'limit': 10, 'offset': 0})
    assert runs.status_code == 200
    assert runs.json()['totalCount'] == 1
    assert runs.json()['runs'][0]['id'] == 'run-001'

    datasets = client.get('/api/v1/namespaces/demo/datasets', params={'limit': 20, 'offset': 0})
    assert datasets.status_code == 200
    datasets_payload = datasets.json()
    assert datasets_payload['totalCount'] == 2
    assert {item['name'] for item in datasets_payload['datasets']} == {'training_dataset', 'model_artifact'}

    dataset = client.get('/api/v1/namespaces/demo/datasets/model_artifact')
    assert dataset.status_code == 200
    dataset_payload = dataset.json()
    assert dataset_payload['type'] == 'DB_TABLE'
    assert dataset_payload['facets']['mlflow_model']['artifact_type'] == 'model'
    assert dataset_payload['columnLineage'] is None

    versions = client.get('/api/v1/namespaces/demo/datasets/model_artifact/versions', params={'limit': 10, 'offset': 0})
    assert versions.status_code == 200
    assert versions.json()['totalCount'] == 1
    assert versions.json()['versions'][0]['createdByRun']['id'] == 'run-001'

    job_facets = client.get('/api/v1/jobs/runs/run-001/facets', params={'type': 'job'})
    assert job_facets.status_code == 200
    assert job_facets.json()['facets']['datajuicer']['recipe'] == 'train_recipe'

    run_facets = client.get('/api/v1/jobs/runs/run-001/facets', params={'type': 'run'})
    assert run_facets.status_code == 200
    assert run_facets.json()['facets']['execution_parameters']['parameters']['epochs'] == 2

    namespaces = client.get('/api/v1/namespaces')
    assert namespaces.status_code == 200
    assert namespaces.json()['namespaces'][0]['name'] == 'demo'

    tags = client.get('/api/v1/tags')
    assert tags.status_code == 200
    assert tags.json() == {'tags': []}


def test_lineage_endpoint_accepts_static_job_and_dataset_events(client: TestClient) -> None:
    dataset_response = client.post('/api/v1/lineage', json=load_event('dataset_event.json'))
    job_response = client.post('/api/v1/lineage', json=load_event('job_event.json'))

    assert dataset_response.status_code == 201
    assert dataset_response.json()['status'] == IngestionStatus.ACCEPTED.value
    assert dataset_response.json()['projected'] is True

    assert job_response.status_code == 201
    assert job_response.json()['status'] == IngestionStatus.ACCEPTED.value
    assert job_response.json()['projected'] is True


def test_lineage_events_endpoint_returns_raw_openlineage_payloads(client: TestClient) -> None:
    client.post('/api/v1/lineage', json=load_event('run_complete.json')).raise_for_status()

    response = client.get('/api/v1/events/lineage', params={'limit': 10})
    assert response.status_code == 200

    payload = response.json()
    assert payload['totalCount'] == 1
    assert len(payload['events']) == 1

    event = payload['events'][0]
    assert event['eventType'] == 'COMPLETE'
    assert event['eventTime'] == '2026-04-23T12:05:00Z'
    assert event['run']['runId'] == 'run-001'
    assert event['job']['name'] == 'train_model'
    assert event['job']['namespace'] == 'demo'
    assert 'payload' not in event
    assert 'run_id' not in event


def test_jobs_endpoint_normalizes_list_style_execution_parameters(client: TestClient) -> None:
    payload = load_event('run_complete.json')
    payload['run']['facets']['execution_parameters']['parameters'] = [
        {'key': 'project_name', 'value': 'demo_project'},
        {'key': 'operators', 'value': '7'},
    ]

    client.post('/api/v1/lineage', json=payload).raise_for_status()

    response = client.get('/api/v1/namespaces/demo/jobs', params={'limit': 25, 'offset': 0})
    assert response.status_code == 200

    latest_run = response.json()['jobs'][0]['latestRun']
    assert latest_run['args'] == {
        'project_name': 'demo_project',
        'operators': '7',
    }


def test_dataset_routes_support_path_like_dataset_names(client: TestClient) -> None:
    path_dataset_name = '/Users/dludora/Code/data-juicer/demos/data/demo-dataset_1725870628.jsonl'
    payload = load_event('dataset_event.json')
    payload['dataset']['namespace'] = 'file'
    payload['dataset']['name'] = path_dataset_name

    client.post('/api/v1/lineage', json=payload).raise_for_status()

    dataset_response = client.get(
        f'/api/v1/namespaces/file/datasets/{path_dataset_name}'
    )
    assert dataset_response.status_code == 200
    assert dataset_response.json()['name'] == path_dataset_name

    versions_response = client.get(
        f'/api/v1/namespaces/file/datasets/{path_dataset_name}/versions',
        params={'limit': 10, 'offset': 0},
    )
    assert versions_response.status_code == 200
    assert versions_response.json()['totalCount'] == 0


def test_lineage_endpoint_accepts_depth_six_for_marquez_web(client: TestClient) -> None:
    client.post('/api/v1/lineage', json=load_event('run_complete.json')).raise_for_status()

    response = client.get(
        '/api/v1/lineage',
        params={'nodeId': 'job:demo:train_model', 'depth': 6},
    )

    assert response.status_code == 200
    assert len(response.json()['graph']) >= 1


def test_routes_and_lineage_support_path_like_namespaces(client: TestClient) -> None:
    namespace = 'inmemory://ffb0ef0c-8c78-55de-a27b-0f9e93a20a10'
    dataset_name = 'op_002_output'
    payload = load_event('dataset_event.json')
    payload['dataset']['namespace'] = namespace
    payload['dataset']['name'] = dataset_name

    client.post('/api/v1/lineage', json=payload).raise_for_status()

    encoded_namespace = quote(namespace, safe='')
    encoded_dataset_name = quote(dataset_name, safe='')

    dataset_response = client.get(
        f'/api/v1/namespaces/{encoded_namespace}/datasets/{encoded_dataset_name}'
    )
    assert dataset_response.status_code == 200
    assert dataset_response.json()['namespace'] == namespace
    assert dataset_response.json()['name'] == dataset_name

    list_response = client.get(
        f'/api/v1/namespaces/{encoded_namespace}/datasets',
        params={'limit': 20, 'offset': 0},
    )
    assert list_response.status_code == 200
    assert list_response.json()['datasets'][0]['namespace'] == namespace

    lineage_response = client.get(
        '/api/v1/lineage',
        params={'nodeId': f'dataset:{namespace}:{dataset_name}', 'depth': 1},
    )
    assert lineage_response.status_code == 200
    assert lineage_response.json()['graph'][0]['id'] == f'dataset:{namespace}:{dataset_name}'
