from __future__ import annotations

from pathlib import Path

from app.execution.task_runners import datajuicer_command, materialize_recipe, task_env
from app.models.api import TaskClaimPayload


def test_materialize_recipe_writes_datajuicer_yaml_with_submission_parameters(tmp_path: Path) -> None:
    task = TaskClaimPayload(
        taskId="task-1",
        attemptId="attempt-1",
        leaseToken="lease-1",
        taskKind="dj_recipe",
        submission={
            'parameters': {
                'np': 4,
                'export_path': '/data/clean.jsonl',
            }
        },
        recipeVersion={
            'id': 'rv-1',
            'recipeId': 'r-1',
            'versionNumber': 1,
            'recipeBody': {
                'project_name': 'clean_sft',
                'dataset_path': '/data/raw.jsonl',
            },
            'command': 'dj-process --config recipe.yaml',
            'scriptPath': '/tmp/recipe.yaml',
            'parameterSchema': {},
            'envTemplate': {},
            'executionSpec': {},
            'timeoutSeconds': 3600,
            'createdBy': 'alice',
            'createdAt': '2026-04-30T00:00:00Z',
        },
        executionSpec={},
        envVars={},
        command='dj-process --config recipe.yaml',
        timeoutSeconds=3600,
    )

    recipe_path = materialize_recipe(task, tmp_path / 'task-1')

    assert recipe_path.name == 'recipe.yaml'
    assert recipe_path.read_text(encoding='utf-8') == (
        'project_name: clean_sft\n'
        'dataset_path: /data/raw.jsonl\n'
        'np: 4\n'
        'export_path: /data/clean.jsonl\n'
    )


def test_datajuicer_command_uses_config_arg_and_extra_args(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'recipe.yaml'

    command = datajuicer_command(
        'dj-process',
        recipe_path,
        {'configArg': '--config', 'extraArgs': ['--debug']},
    )

    assert command == ['dj-process', '--config', str(recipe_path), '--debug']


def test_task_env_points_openlineage_to_backend() -> None:
    task = TaskClaimPayload(
        taskId="task-1",
        attemptId="attempt-1",
        leaseToken="lease-1",
        taskKind="training",
        submission={},
        recipeVersion=None,
        executionSpec={},
        envVars={'DJ_ENV': 'dev', 'COUNT': 3},
        command='python train.py',
        timeoutSeconds=3600,
    )
    env = task_env(
        'http://127.0.0.1:8000/',
        task,
    )

    assert env['OPENLINEAGE_URL'] == 'http://127.0.0.1:8000/api/v1/lineage'
    assert env['DJ_ENV'] == 'dev'
    assert env['COUNT'] == '3'
