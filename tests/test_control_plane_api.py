from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from dj_panel.app.api.dependencies import (
    get_asset_service,
    get_lineage_service,
    get_recipe_service,
    get_run_submission_service,
    get_task_service,
    get_worker_service,
    get_workspace_service,
)
from dj_panel.app.db.engine import get_engine
from dj_panel.app.db.schema import execution_links, metadata
from dj_panel.app.main import app
from dj_panel.app.services.assets_service import AssetService
from dj_panel.app.services.lineage_service import LineageService
from dj_panel.app.services.recipes_service import RecipeService
from dj_panel.app.services.run_submissions_service import RunSubmissionService
from dj_panel.app.services.tasks_service import TaskService
from dj_panel.app.services.workers_service import WorkerService
from dj_panel.app.services.workspaces_service import WorkspaceService

FIXTURES = Path(__file__).parent / "fixtures"


def load_event(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def make_client() -> TestClient:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        future=True,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_asset_service] = lambda: AssetService(engine)
    app.dependency_overrides[get_lineage_service] = lambda: LineageService(engine)
    app.dependency_overrides[get_workspace_service] = lambda: WorkspaceService(engine)
    app.dependency_overrides[get_recipe_service] = lambda: RecipeService(engine)
    app.dependency_overrides[get_run_submission_service] = lambda: RunSubmissionService(engine)
    app.dependency_overrides[get_worker_service] = lambda: WorkerService(engine)
    app.dependency_overrides[get_task_service] = lambda: TaskService(engine)
    client = TestClient(app)
    client.engine = engine  # type: ignore[attr-defined]

    def cleanup() -> None:
        app.dependency_overrides.clear()
        metadata.drop_all(engine)

    client.cleanup = cleanup  # type: ignore[attr-defined]
    return client


def create_workspace(client: TestClient, slug: str = 'team-a') -> dict:
    response = client.post('/api/v1/workspaces', json={'slug': slug, 'name': slug.upper(), 'description': ''})
    response.raise_for_status()
    return response.json()


def create_recipe(client: TestClient, workspace_slug: str, name: str = 'demo-recipe') -> dict:
    response = client.post(
        f'/api/v1/workspaces/{workspace_slug}/recipes',
        json={
            'name': name,
            'description': 'demo recipe',
            'ownerName': 'alice',
            'recipeBody': {'steps': ['load', 'train']},
            'command': 'python run_demo.py --epochs 3',
            'scriptPath': '/tmp/run_demo.py',
            'parameterSchema': {'type': 'object'},
            'envTemplate': {'DJ_ENV': 'dev'},
            'executionSpec': {'entrypoint': 'python'},
            'timeoutSeconds': 120,
        },
    )
    response.raise_for_status()
    return response.json()


def create_dataset(
    client: TestClient,
    *,
    namespace: str,
    name: str,
    facets: dict | None = None,
) -> dict:
    response = client.post(
        '/api/v1/assets',
        json={
            'namespace': namespace,
            'name': name,
            'assetKind': 'DATASET',
            'description': '',
            'facets': facets or {},
        },
    )
    response.raise_for_status()
    return response.json()


def test_control_plane_happy_path() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-a')
        recipe = create_recipe(client, workspace['slug'])

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'manager',
                'parameters': {'epochs': 5, 'learning_rate': '0.01'},
            },
        )
        run_response.raise_for_status()
        run_submission = run_response.json()['submission']
        assert run_submission['status'] == 'PENDING'

        worker_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'worker-1',
                'displayName': 'Worker 1',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'local-shell'},
                'maxConcurrency': 1,
            },
        )
        worker_response.raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-1'},
        )
        claim_response.raise_for_status()
        claim = claim_response.json()
        assert claim['claimed'] is True
        assert claim['task']['recipeVersion']['id'] == recipe['currentVersion']['id']
        assert claim['task']['envVars']['epochs'] == 5
        assert claim['task']['command'] == 'python run_demo.py --epochs 3'
        assert claim['task']['taskKind'] == 'dj_recipe'

        second_claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-1'},
        )
        second_claim.raise_for_status()
        assert second_claim.json() == {'claimed': False, 'task': None}

        task_id = claim['task']['taskId']
        attempt_id = claim['task']['attemptId']
        lease_token = claim['task']['leaseToken']

        start_response = client.post(
            f'/api/v1/tasks/{task_id}/start',
            json={
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'openlineageRunId': 'ol-run-1',
                'rootLineageNodeId': 'job:demo:demo.train',
            },
        )
        start_response.raise_for_status()
        assert start_response.json()['status'] == 'RUNNING'
        assert start_response.json()['currentAttempt']['openlineageRunId'] == 'ol-run-1'
        assert start_response.json()['currentAttempt']['executionLink']['openlineageRunId'] == 'ol-run-1'

        artifact_response = client.post(
            f'/api/v1/task-attempts/{attempt_id}/artifacts',
            json={
                'kind': 'MODEL',
                'name': 'trained-model',
                'uri': 'mlflow://runs/mlflow-run-1/artifacts/model',
                'metadata': {'stage': 'staging'},
                'modelUri': 'models:/demo-model/1',
            },
        )
        artifact_response.raise_for_status()
        assert artifact_response.json()['modelUri'] == 'models:/demo-model/1'

        complete_response = client.post(
            f'/api/v1/tasks/{task_id}/complete',
            json={
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'openlineageRunId': 'ol-run-1',
                'rootLineageNodeId': 'job:demo:demo.train',
            },
        )
        complete_response.raise_for_status()
        assert complete_response.json()['status'] == 'SUCCEEDED'

        submissions = client.get(f"/api/v1/workspaces/{workspace['slug']}/run-submissions")
        submissions.raise_for_status()
        assert submissions.json()['submissions'][0]['status'] == 'SUCCEEDED'

        tasks = client.get(f"/api/v1/workspaces/{workspace['slug']}/tasks")
        tasks.raise_for_status()
        assert tasks.json()['tasks'][0]['currentAttempt']['openlineageRunId'] == 'ol-run-1'
        assert tasks.json()['tasks'][0]['currentAttempt']['executionLink']['openlineageRunId'] == 'ol-run-1'

        artifacts = client.get(f'/api/v1/task-attempts/{attempt_id}/artifacts')
        artifacts.raise_for_status()
        assert artifacts.json()['artifacts'][0]['kind'] == 'MODEL'

        with client.engine.begin() as conn:  # type: ignore[attr-defined]
            link = conn.execute(select(execution_links)).mappings().one()
            assert link['task_attempt_id'] == attempt_id
            assert link['openlineage_run_id'] == 'ol-run-1'
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_failed_run_submission_can_be_resumed_with_same_task_and_new_attempt() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-resume')
        recipe = create_recipe(client, workspace['slug'], 'resume-recipe')

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'alice',
                'parameters': {'epochs': 2},
            },
        )
        run_response.raise_for_status()
        submission = run_response.json()['submission']

        worker_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'worker-resume',
                'displayName': 'Worker Resume',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'local-shell'},
                'maxConcurrency': 1,
            },
        )
        worker_response.raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-resume'},
        )
        claim_response.raise_for_status()
        claim = claim_response.json()['task']
        task_id = claim['taskId']
        first_attempt_id = claim['attemptId']

        fail_response = client.post(
            f"/api/v1/tasks/{task_id}/fail",
            json={
                'attemptId': first_attempt_id,
                'leaseToken': claim['leaseToken'],
                'failureReason': 'boom',
            },
        )
        fail_response.raise_for_status()
        assert fail_response.json()['status'] == 'FAILED'

        resume_response = client.post(f"/api/v1/run-submissions/{submission['id']}/resume")
        resume_response.raise_for_status()
        resumed = resume_response.json()['submission']
        assert resumed['id'] == submission['id']
        assert resumed['status'] == 'PENDING'
        assert resumed['startedAt'] is None
        assert resumed['endedAt'] is None
        assert resumed['failureReason'] is None
        assert resumed['rootLineageNodeId'] is None

        task_response = client.get(f"/api/v1/tasks/{task_id}")
        task_response.raise_for_status()
        task = task_response.json()
        assert task['id'] == task_id
        assert task['status'] == 'PENDING'
        assert task['currentAttemptId'] is None
        assert task['attemptCount'] == 1
        assert task['failureReason'] is None

        reclaim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-resume'},
        )
        reclaim_response.raise_for_status()
        reclaim = reclaim_response.json()['task']
        assert reclaim['taskId'] == task_id
        assert reclaim['attemptId'] != first_attempt_id

        second_task_response = client.get(f"/api/v1/tasks/{task_id}")
        second_task_response.raise_for_status()
        second_task = second_task_response.json()
        assert second_task['attemptCount'] == 2
        assert second_task['currentAttempt']['attemptNumber'] == 2
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_pending_run_submission_can_be_cancelled() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-cancel')
        recipe = create_recipe(client, workspace['slug'], 'cancel-recipe')

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'alice',
            },
        )
        run_response.raise_for_status()
        submission = run_response.json()['submission']

        cancel_response = client.post(f"/api/v1/run-submissions/{submission['id']}/cancel")
        cancel_response.raise_for_status()
        cancelled = cancel_response.json()['submission']
        assert cancelled['status'] == 'CANCELLED'
        assert cancelled['endedAt'] is not None
        assert cancelled['failureReason'] == 'Cancelled by user'

        tasks_response = client.get(f"/api/v1/workspaces/{workspace['slug']}/tasks")
        tasks_response.raise_for_status()
        task = tasks_response.json()['tasks'][0]
        assert task['status'] == 'CANCELLED'
        assert task['endedAt'] is not None
        assert task['failureReason'] == 'Cancelled by user'

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'worker-cancel',
                'displayName': 'Worker Cancel',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'local-shell'},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-cancel'},
        )
        claim_response.raise_for_status()
        assert claim_response.json() == {'claimed': False, 'task': None}
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_non_pending_run_submission_cannot_be_cancelled() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-cancel-nope')
        recipe = create_recipe(client, workspace['slug'], 'cancel-nope')

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'alice',
            },
        )
        run_response.raise_for_status()
        submission = run_response.json()['submission']

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'worker-cancel-nope',
                'displayName': 'Worker Cancel Nope',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'local-shell'},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-cancel-nope'},
        )
        claim_response.raise_for_status()
        claim = claim_response.json()['task']

        start_response = client.post(
            f"/api/v1/tasks/{claim['taskId']}/start",
            json={
                'attemptId': claim['attemptId'],
                'leaseToken': claim['leaseToken'],
            },
        )
        start_response.raise_for_status()
        assert start_response.json()['status'] == 'RUNNING'

        cancel_response = client.post(f"/api/v1/run-submissions/{submission['id']}/cancel")
        assert cancel_response.status_code == 409
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_succeeded_run_submission_cannot_be_resumed() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-resume-nope')
        recipe = create_recipe(client, workspace['slug'], 'resume-nope')

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'alice',
            },
        )
        run_response.raise_for_status()
        submission = run_response.json()['submission']

        worker_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'worker-success',
                'displayName': 'Worker Success',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'local-shell'},
                'maxConcurrency': 1,
            },
        )
        worker_response.raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'worker-success'},
        )
        claim_response.raise_for_status()
        claim = claim_response.json()['task']

        complete_response = client.post(
            f"/api/v1/tasks/{claim['taskId']}/complete",
            json={
                'attemptId': claim['attemptId'],
                'leaseToken': claim['leaseToken'],
            },
        )
        complete_response.raise_for_status()
        assert complete_response.json()['status'] == 'SUCCEEDED'

        resume_response = client.post(f"/api/v1/run-submissions/{submission['id']}/resume")
        assert resume_response.status_code == 409
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_workspace_members_can_be_created_and_listed() -> None:
    client = make_client()
    try:
        response = client.post(
            '/api/v1/workspaces',
            json={
                'slug': 'team-members',
                'name': 'Team Members',
                'description': '',
                'ownerName': 'alice',
            },
        )
        response.raise_for_status()

        add_response = client.post(
            '/api/v1/workspaces/team-members/members',
            json={'userName': 'bob', 'role': 'MAINTAINER'},
        )
        add_response.raise_for_status()
        assert add_response.json()['role'] == 'MAINTAINER'

        update_response = client.post(
            '/api/v1/workspaces/team-members/members',
            json={'userName': 'bob', 'role': 'MEMBER'},
        )
        update_response.raise_for_status()
        assert update_response.json()['role'] == 'MEMBER'

        list_response = client.get('/api/v1/workspaces/team-members/members')
        list_response.raise_for_status()
        members = list_response.json()['members']
        assert {member['userName']: member['role'] for member in members} == {
            'alice': 'OWNER',
            'bob': 'MEMBER',
        }
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_recipe_version_create_accepts_camel_case_payload() -> None:
    client = make_client()
    try:
        create_workspace(client, 'team-a')
        recipe = create_recipe(client, 'team-a', 'camel-recipe')

        response = client.post(
            f"/api/v1/recipes/{recipe['id']}/versions",
            json={
                'createdBy': 'alice',
                'recipeBody': {'project_name': 'camel-recipe-v2'},
                'command': 'dj-process --config recipe.yaml',
                'scriptPath': '/tmp/recipe.yaml',
                'parameterSchema': {},
                'envTemplate': {},
                'executionSpec': {'taskKind': 'dj_recipe'},
                'timeoutSeconds': 7200,
            },
        )
        response.raise_for_status()
        version = response.json()
        assert version['versionNumber'] == 2
        assert version['scriptPath'] == '/tmp/recipe.yaml'
        assert version['createdBy'] == 'alice'
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_training_submission_creates_command_task() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-train')

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'training',
                'name': 'qwen2-sft-v1',
                'requestedBy': 'alice',
                'spec': {
                    'name': 'qwen2-sft-v1',
                    'command': 'python train.py --config train.yaml',
                    'workdir': '/tmp/llm-trainer',
                    'env': {
                        'MLFLOW_TRACKING_URI': 'http://127.0.0.1:5000',
                        'MLFLOW_EXPERIMENT_NAME': 'qwen2-sft',
                    },
                    'timeoutSeconds': 7200,
                },
                'inputs': [{'uri': '/data/processed/train.jsonl'}],
                'outputs': [{'uri': '/data/models/qwen2-sft-v1'}],
            },
        )
        run_response.raise_for_status()
        submission = run_response.json()['submission']
        assert submission['submissionKind'] == 'training'
        assert submission['name'] == 'qwen2-sft-v1'
        assert submission['recipeId'] is None
        assert submission['recipeVersionId'] is None
        assert submission['spec']['command'] == 'python train.py --config train.yaml'

        worker_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'train-worker-1',
                'displayName': 'Train Worker 1',
                'labels': {'zone': 'local'},
                'capabilities': {'execution': 'command', 'taskKinds': ['training']},
                'maxConcurrency': 1,
            },
        )
        worker_response.raise_for_status()

        claim_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'train-worker-1', 'supportedTaskKinds': ['training']},
        )
        claim_response.raise_for_status()
        claim = claim_response.json()
        assert claim['claimed'] is True
        assert claim['task']['taskKind'] == 'training'
        assert claim['task']['recipeVersion'] is None
        assert claim['task']['command'] == 'python train.py --config train.yaml'
        assert claim['task']['executionSpec']['workdir'] == '/tmp/llm-trainer'
        assert claim['task']['envVars']['MLFLOW_EXPERIMENT_NAME'] == 'qwen2-sft'
        assert claim['task']['submission']['submissionKind'] == 'training'
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_execution_link_attaches_to_projected_lineage_run() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, "team-link")
        recipe = create_recipe(client, workspace["slug"], "link-recipe")

        run_response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                "recipeVersionId": recipe["currentVersion"]["id"],
                "requestedBy": "alice",
                "parameters": {},
            },
        )
        run_response.raise_for_status()

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                "workerId": "worker-link",
                "displayName": "Worker Link",
                "labels": {},
                "capabilities": {},
                "maxConcurrency": 1,
            },
        ).raise_for_status()

        claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={"workerId": "worker-link"},
        )
        claim.raise_for_status()
        payload = claim.json()["task"]

        start = client.post(
            f"/api/v1/tasks/{payload['taskId']}/start",
            json={
                "attemptId": payload["attemptId"],
                "leaseToken": payload["leaseToken"],
            },
        )
        start.raise_for_status()
        assert start.json()["currentAttempt"]["openlineageRunId"] is None
        assert start.json()["currentAttempt"]["executionLink"] is None

        event = load_event("run_complete.json")
        event["run"]["runId"] = "ol-run-attach-1"
        event["run"]["facets"]["datajuicer"] = {"jobId": payload["taskId"]}
        client.post("/api/v1/lineage", json=event).raise_for_status()

        task = client.get(f"/api/v1/tasks/{payload['taskId']}")
        task.raise_for_status()
        assert task.json()["currentAttempt"]["openlineageRunId"] == "ol-run-attach-1"
        link = task.json()["currentAttempt"]["executionLink"]
        assert link["openlineageRunId"] == "ol-run-attach-1"
        assert link["lineageRunId"] is not None
        assert link["lineageJobId"] is not None
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_operator_run_with_parent_facet_does_not_bind_task() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, "team-operator")
        recipe = create_recipe(client, workspace["slug"], "operator-recipe")

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                "recipeVersionId": recipe["currentVersion"]["id"],
                "requestedBy": "alice",
                "parameters": {},
            },
        ).raise_for_status()

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                "workerId": "worker-operator",
                "displayName": "Worker Operator",
                "labels": {},
                "capabilities": {},
                "maxConcurrency": 1,
            },
        ).raise_for_status()

        claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={"workerId": "worker-operator"},
        )
        claim.raise_for_status()
        payload = claim.json()["task"]

        event = load_event("run_complete.json")
        event["run"]["runId"] = "ol-run-operator-1"
        event["run"]["facets"]["datajuicer"] = {"jobId": payload["taskId"]}
        event["run"]["facets"]["parent"] = {
            "run": {"runId": "pipeline-run-1"},
            "job": {"namespace": "demo", "name": "pipeline-job"},
            "root": {
                "run": {"runId": "pipeline-run-1"},
                "job": {"namespace": "demo", "name": "pipeline-job"},
            },
        }
        client.post("/api/v1/lineage", json=event).raise_for_status()

        task = client.get(f"/api/v1/tasks/{payload['taskId']}")
        task.raise_for_status()
        assert task.json()["currentAttempt"]["openlineageRunId"] is None
        assert task.json()["currentAttempt"]["executionLink"] is None
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_lineage_ingest_ignores_missing_task_binding() -> None:
    client = make_client()
    try:
        event = load_event("run_complete.json")
        event["run"]["runId"] = "ol-run-missing-task-1"
        event["run"]["facets"]["datajuicer"] = {"jobId": "missing-task-id"}
        response = client.post("/api/v1/lineage", json=event)
        response.raise_for_status()

        with client.engine.begin() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(select(execution_links)).mappings().all()
            assert rows == []
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_recipe_create_rejects_snake_case_payload() -> None:
    client = make_client()
    try:
        create_workspace(client, 'team-a')
        response = client.post(
            '/api/v1/workspaces/team-a/recipes',
            json={
                'name': 'snake-recipe',
                'description': 'should fail',
                'owner_name': 'alice',
                'recipe_body': {'project_name': 'snake-recipe'},
                'command': 'dj-process --config recipe.yaml',
                'script_path': '/tmp/recipe.yaml',
            },
        )
        assert response.status_code == 422
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_workspace_isolation_for_claims() -> None:
    client = make_client()
    try:
        create_workspace(client, 'team-a')
        create_workspace(client, 'team-b')
        recipe = create_recipe(client, 'team-a', 'team-a-recipe')
        client.post(
            '/api/v1/workspaces/team-a/run-submissions',
            json={'recipeVersionId': recipe['currentVersion']['id'], 'requestedBy': 'manager', 'parameters': {}},
        ).raise_for_status()
        client.post(
            '/api/v1/workspaces/team-b/workers/register',
            json={
                'workerId': 'worker-b',
                'displayName': 'Worker B',
                'labels': {},
                'capabilities': {},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        response = client.post('/api/v1/workspaces/team-b/tasks/claim', json={'workerId': 'worker-b'})
        response.raise_for_status()
        assert response.json() == {'claimed': False, 'task': None}
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_claim_is_single_winner() -> None:
    client = make_client()
    try:
        create_workspace(client, 'team-a')
        recipe = create_recipe(client, 'team-a', 'single-winner')
        client.post(
            '/api/v1/workspaces/team-a/run-submissions',
            json={'recipeVersionId': recipe['currentVersion']['id'], 'requestedBy': 'manager', 'parameters': {}},
        ).raise_for_status()
        for worker_id in ('worker-1', 'worker-2'):
            client.post(
                '/api/v1/workspaces/team-a/workers/register',
                json={
                    'workerId': worker_id,
                    'displayName': worker_id,
                    'labels': {},
                    'capabilities': {},
                    'maxConcurrency': 1,
                },
            ).raise_for_status()

        first = client.post('/api/v1/workspaces/team-a/tasks/claim', json={'workerId': 'worker-1'})
        second = client.post('/api/v1/workspaces/team-a/tasks/claim', json={'workerId': 'worker-2'})
        first.raise_for_status()
        second.raise_for_status()

        assert first.json()['claimed'] != second.json()['claimed']
        winner = first.json() if first.json()['claimed'] else second.json()
        assert winner['task']['taskId']
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_run_submissions_create_claimable_task() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-a')
        recipe = create_recipe(client, workspace['slug'], 'submission-recipe')

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'manager',
                'parameters': {'sample_size': 10},
            },
        )
        response.raise_for_status()
        submission = response.json()['submission']
        assert submission['submissionKind'] == 'processing'
        assert submission['status'] == 'PENDING'

        list_response = client.get(f"/api/v1/workspaces/{workspace['slug']}/run-submissions")
        list_response.raise_for_status()
        assert list_response.json()['submissions'][0]['id'] == submission['id']

        detail_response = client.get(f"/api/v1/run-submissions/{submission['id']}")
        detail_response.raise_for_status()
        assert detail_response.json()['submission']['requestedBy'] == 'manager'
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_processing_spec_workspace_recipe_creates_dj_task() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-process')
        recipe = create_recipe(client, workspace['slug'], 'process-recipe')

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'requestedBy': 'alice',
                'spec': {
                    'kind': 'processing',
                    'name': 'process-run-1',
                    'process': {
                        'dj_configs': {
                            'mode': 'workspace_recipe',
                            'name': 'process-recipe',
                            'versionId': recipe['currentVersion']['id'],
                        },
                        'extra_configs': {'sample_size': 3},
                        'env': {'DJ_ENV': 'prod'},
                        'timeoutSeconds': 180,
                    },
                },
            },
        )
        response.raise_for_status()
        submission = response.json()['submission']
        assert submission['submissionKind'] == 'processing'
        assert submission['name'] == 'process-run-1'
        assert submission['recipeVersionId'] == recipe['currentVersion']['id']

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'dj-worker-1',
                'displayName': 'DJ Worker 1',
                'labels': {},
                'capabilities': {'taskKinds': ['dj_recipe']},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'dj-worker-1', 'supportedTaskKinds': ['dj_recipe']},
        )
        claim.raise_for_status()
        payload = claim.json()['task']
        assert payload['submission']['parameters'] == {'sample_size': 3}
        assert payload['envVars']['DJ_ENV'] == 'prod'
        assert payload['recipeVersion']['id'] == recipe['currentVersion']['id']
        assert payload['timeoutSeconds'] == 180
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_processing_spec_local_file_creates_materializable_dj_task() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-process-file')
        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'requestedBy': 'alice',
                'spec': {
                    'kind': 'processing',
                    'name': 'process-file-run',
                    'process': {
                        'dj_configs': {
                            'mode': 'local_file',
                            'path': '/tmp/process.yaml',
                            'recipeBody': {
                                'project_name': 'process-file-run',
                                'dataset_path': '/data/raw.jsonl',
                                'export_path': '/data/out.jsonl',
                            },
                        },
                        'extra_configs': {'export_path': '/data/final.jsonl'},
                        'env': {'DJ_ENV': 'dev'},
                    },
                },
            },
        )
        response.raise_for_status()

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'dj-worker-2',
                'displayName': 'DJ Worker 2',
                'labels': {},
                'capabilities': {'taskKinds': ['dj_recipe']},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'dj-worker-2', 'supportedTaskKinds': ['dj_recipe']},
        )
        claim.raise_for_status()
        payload = claim.json()['task']
        assert payload['recipeVersion'] is None
        assert payload['submission']['parameters'] == {'export_path': '/data/final.jsonl'}
        assert payload['executionSpec']['recipeBody']['project_name'] == 'process-file-run'
        assert payload['executionSpec']['recipeBody']['dataset_path'] == '/data/raw.jsonl'
        assert payload['envVars']['DJ_ENV'] == 'dev'
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_processing_spec_dataset_inputs_resolve_to_dataset_configs() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-process-datasets')
        recipe = create_recipe(client, workspace['slug'], 'process-recipe')
        create_dataset(
            client,
            namespace='llm-team.datasets',
            name='raw_sft',
            facets={
                'datajuicerInput': {
                    'inputConfig': {
                        'type': 'local',
                        'path': '/data/raw_sft.jsonl',
                        'format': 'jsonl',
                    }
                }
            },
        )

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'requestedBy': 'alice',
                'spec': {
                    'kind': 'processing',
                    'name': 'process-run-dataset-ref',
                    'process': {
                        'dj_configs': {
                            'mode': 'workspace_recipe',
                            'name': 'process-recipe',
                            'versionId': recipe['currentVersion']['id'],
                        },
                        'datasets': {
                            'inputs': [
                                {'namespace': 'llm-team.datasets', 'name': 'raw_sft'}
                            ]
                        },
                        'extra_configs': {'export_path': '/data/final.jsonl'},
                    },
                },
            },
        )
        response.raise_for_status()

        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'dj-worker-dataset-ref',
                'displayName': 'DJ Worker Dataset Ref',
                'labels': {},
                'capabilities': {'taskKinds': ['dj_recipe']},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        claim = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'dj-worker-dataset-ref', 'supportedTaskKinds': ['dj_recipe']},
        )
        claim.raise_for_status()
        payload = claim.json()['task']
        assert payload['submission']['parameters']['export_path'] == '/data/final.jsonl'
        assert payload['submission']['parameters']['dataset'] == {
            'configs': [
                {
                    'type': 'local',
                    'path': '/data/raw_sft.jsonl',
                    'format': 'jsonl',
                }
            ]
        }
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_processing_spec_dataset_inputs_require_input_config() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-process-datasets-missing')
        recipe = create_recipe(client, workspace['slug'], 'process-recipe')
        create_dataset(
            client,
            namespace='llm-team.datasets',
            name='raw_sft_missing',
            facets={'dataSource': {'uri': '/data/raw_sft.jsonl'}},
        )

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'requestedBy': 'alice',
                'spec': {
                    'kind': 'processing',
                    'name': 'process-run-dataset-ref',
                    'process': {
                        'dj_configs': {
                            'mode': 'workspace_recipe',
                            'name': 'process-recipe',
                            'versionId': recipe['currentVersion']['id'],
                        },
                        'datasets': {
                            'inputs': [
                                {
                                    'namespace': 'llm-team.datasets',
                                    'name': 'raw_sft_missing',
                                }
                            ]
                        },
                    },
                },
            },
        )
        assert response.status_code == 404
        assert 'facets.datajuicerInput.inputConfig' in response.text
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_processing_spec_dataset_inputs_conflict_with_dataset_path() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-process-datasets-conflict')
        recipe = create_recipe(client, workspace['slug'], 'process-recipe')
        create_dataset(
            client,
            namespace='llm-team.datasets',
            name='raw_sft',
            facets={
                'datajuicerInput': {
                    'inputConfig': {
                        'type': 'local',
                        'path': '/data/raw_sft.jsonl',
                    }
                }
            },
        )

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'submissionKind': 'processing',
                'requestedBy': 'alice',
                'spec': {
                    'kind': 'processing',
                    'name': 'process-run-dataset-ref',
                    'process': {
                        'dj_configs': {
                            'mode': 'workspace_recipe',
                            'name': 'process-recipe',
                            'versionId': recipe['currentVersion']['id'],
                        },
                        'datasets': {
                            'inputs': [
                                {'namespace': 'llm-team.datasets', 'name': 'raw_sft'}
                            ]
                        },
                        'extra_configs': {'dataset_path': '/data/raw.jsonl'},
                    },
                },
            },
        )
        assert response.status_code == 404
        assert 'process.datasets.inputs cannot be used together with process.extra_configs.dataset_path' in response.text
    finally:
        client.cleanup()  # type: ignore[attr-defined]


def test_claim_can_filter_by_supported_task_kind() -> None:
    client = make_client()
    try:
        workspace = create_workspace(client, 'team-a')
        recipe = create_recipe(client, workspace['slug'], 'kind-filter')
        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/run-submissions",
            json={
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'manager',
                'parameters': {},
            },
        ).raise_for_status()
        client.post(
            f"/api/v1/workspaces/{workspace['slug']}/workers/register",
            json={
                'workerId': 'dj-worker',
                'displayName': 'DJ Worker',
                'labels': {},
                'capabilities': {'taskKinds': ['dj_recipe']},
                'maxConcurrency': 1,
            },
        ).raise_for_status()

        response = client.post(
            f"/api/v1/workspaces/{workspace['slug']}/tasks/claim",
            json={'workerId': 'dj-worker', 'supportedTaskKinds': ['dj_recipe']},
        )
        response.raise_for_status()
        claim = response.json()
        assert claim['claimed'] is True
        assert claim['task']['taskKind'] == 'dj_recipe'
    finally:
        client.cleanup()  # type: ignore[attr-defined]
