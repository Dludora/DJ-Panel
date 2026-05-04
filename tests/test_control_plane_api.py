from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import (
    get_recipe_service,
    get_run_submission_service,
    get_task_service,
    get_worker_service,
    get_workspace_service,
)
from app.db.schema import metadata
from app.main import app
from app.services.recipes import RecipeService
from app.services.run_submissions import RunSubmissionService
from app.services.tasks import TaskService
from app.services.workers import WorkerService
from app.services.workspaces import WorkspaceService


def make_client() -> TestClient:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        future=True,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    app.dependency_overrides[get_workspace_service] = lambda: WorkspaceService(engine)
    app.dependency_overrides[get_recipe_service] = lambda: RecipeService(engine)
    app.dependency_overrides[get_run_submission_service] = lambda: RunSubmissionService(engine)
    app.dependency_overrides[get_worker_service] = lambda: WorkerService(engine)
    app.dependency_overrides[get_task_service] = lambda: TaskService(engine)
    client = TestClient(app)

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

        artifacts = client.get(f'/api/v1/task-attempts/{attempt_id}/artifacts')
        artifacts.raise_for_status()
        assert artifacts.json()['artifacts'][0]['kind'] == 'MODEL'
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
                'submissionKind': 'processing_pipeline',
                'recipeVersionId': recipe['currentVersion']['id'],
                'requestedBy': 'manager',
                'parameters': {'sample_size': 10},
            },
        )
        response.raise_for_status()
        submission = response.json()['submission']
        assert submission['submissionKind'] == 'processing_pipeline'
        assert submission['status'] == 'PENDING'

        list_response = client.get(f"/api/v1/workspaces/{workspace['slug']}/run-submissions")
        list_response.raise_for_status()
        assert list_response.json()['submissions'][0]['id'] == submission['id']

        detail_response = client.get(f"/api/v1/run-submissions/{submission['id']}")
        detail_response.raise_for_status()
        assert detail_response.json()['submission']['requestedBy'] == 'manager'
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
