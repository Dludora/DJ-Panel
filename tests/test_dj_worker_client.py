from __future__ import annotations

from pathlib import Path

from cli.worker import datajuicer_command, materialize_recipe, task_env


def test_materialize_recipe_writes_datajuicer_yaml_with_submission_parameters(tmp_path: Path) -> None:
    task = {
        'recipeVersion': {
            'recipeBody': {
                'project_name': 'clean_sft',
                'dataset_path': '/data/raw.jsonl',
            },
        },
        'submission': {
            'parameters': {
                'np': 4,
                'export_path': '/data/clean.jsonl',
            },
        },
    }

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
    env = task_env(
        'http://127.0.0.1:8000/',
        {'envVars': {'DJ_ENV': 'dev', 'COUNT': 3}},
    )

    assert env['OPENLINEAGE_URL'] == 'http://127.0.0.1:8000/api/v1/lineage'
    assert env['DJ_ENV'] == 'dev'
    assert env['COUNT'] == '3'
