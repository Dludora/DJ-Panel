from __future__ import annotations

from pathlib import Path

from dj_panel.app.execution.task_runners import (
    datajuicer_command,
    materialize_recipe,
    run_log_path,
    task_env,
    task_runtime_dir,
)
from dj_panel.app.models.api import TaskClaimPayload


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

    task_dir = tmp_path / 'tasks' / 'task-1'
    recipe_path = materialize_recipe(task, task_dir)

    assert recipe_path.name == 'recipe.yaml'
    assert recipe_path.read_text(encoding='utf-8') == (
        'project_name: clean_sft\n'
        'dataset_path: /data/raw.jsonl\n'
        'np: 4\n'
        'export_path: /data/clean.jsonl\n'
        f'work_dir: {tmp_path / "tasks" / "{job_id}"}\n'
    )


def test_datajuicer_command_uses_config_arg_and_extra_args(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'recipe.yaml'

    command = datajuicer_command(
        'dj-process',
        recipe_path,
        {'configArg': '--config', 'extraArgs': ['--debug']},
        'task-1',
    )

    assert command == ['dj-process', '--config', str(recipe_path.resolve()), '--job_id', 'task-1', '--debug']


def test_materialize_recipe_can_use_execution_spec_recipe_body(tmp_path: Path) -> None:
    task = TaskClaimPayload(
        taskId="task-2",
        attemptId="attempt-2",
        leaseToken="lease-2",
        taskKind="dj_recipe",
        submission={'parameters': {'export_path': '/data/final.jsonl'}},
        recipeVersion=None,
        executionSpec={
            'recipeBody': {
                'project_name': 'local-process',
                'dataset_path': '/data/raw.jsonl',
            }
        },
        envVars={},
        command='dj-process --config recipe.yaml',
        timeoutSeconds=3600,
    )

    task_dir = tmp_path / 'tasks' / 'task-2'
    recipe_path = materialize_recipe(task, task_dir)

    assert recipe_path.read_text(encoding='utf-8') == (
        'project_name: local-process\n'
        'dataset_path: /data/raw.jsonl\n'
        'export_path: /data/final.jsonl\n'
        f'work_dir: {tmp_path / "tasks" / "{job_id}"}\n'
    )


def test_materialize_recipe_merges_dataset_configs_from_submission_parameters(tmp_path: Path) -> None:
    task = TaskClaimPayload(
        taskId="task-3",
        attemptId="attempt-3",
        leaseToken="lease-3",
        taskKind="dj_recipe",
        submission={
            'parameters': {
                'dataset': {
                    'configs': [
                        {
                            'type': 'local',
                            'path': '/data/raw.jsonl',
                            'format': 'jsonl',
                        }
                    ]
                },
                'export_path': '/data/final.jsonl',
            }
        },
        recipeVersion=None,
        executionSpec={
            'recipeBody': {
                'project_name': 'local-process',
            }
        },
        envVars={},
        command='dj-process --config recipe.yaml',
        timeoutSeconds=3600,
    )

    task_dir = tmp_path / 'tasks' / 'task-3'
    recipe_path = materialize_recipe(task, task_dir)

    assert recipe_path.read_text(encoding='utf-8') == (
        'project_name: local-process\n'
        'dataset:\n'
        '  configs:\n'
        '  - type: local\n'
        '    path: /data/raw.jsonl\n'
        '    format: jsonl\n'
        'export_path: /data/final.jsonl\n'
        f'work_dir: {tmp_path / "tasks" / "{job_id}"}\n'
    )


def test_task_runtime_dir_and_run_log_use_single_task_directory(tmp_path: Path) -> None:
    runtime_dir = task_runtime_dir(tmp_path / 'panel' / 'demo', 'task-3')

    assert runtime_dir == (tmp_path / 'panel' / 'demo' / 'tasks' / 'task-3').resolve()
    assert run_log_path(runtime_dir) == runtime_dir / 'run.log'


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
