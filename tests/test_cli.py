from __future__ import annotations

from pathlib import Path
import argparse

import pytest

import dj_panel.cli.commands as cli_commands
from dj_panel.cli import (
    DEFAULT_DJ_EXECUTION_SPEC,
    DEFAULT_DJ_COMMAND,
    _build_recipe_create_request,
    _dump_recipe_yaml,
    _load_env_overrides,
    _load_json_arg,
    _load_processing_run_spec,
    _load_recipe_body,
    _load_structured_arg,
    _normalize_base_url,
    _render_config,
    _render_recipe,
    _render_recipe_list,
)


def test_load_recipe_body_requires_yaml_mapping(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'bad.yaml'
    recipe_path.write_text('- one\n- two\n', encoding='utf-8')

    with pytest.raises(ValueError, match='YAML mapping'):
        _load_recipe_body(recipe_path)


def test_build_recipe_create_request_defaults_to_datajuicer_task(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'cleaning.yaml'
    recipe_path.write_text(
        'project_name: sft-cleaning\n'
        'dataset_path: /data/raw.jsonl\n'
        'export_path: /data/clean.jsonl\n',
        encoding='utf-8',
    )

    request = _build_recipe_create_request(
        file=recipe_path,
        name=None,
        description='clean data',
        owner='alice',
        recipe_command_line=DEFAULT_DJ_COMMAND,
        timeout_seconds=7200,
        extra_execution_spec=None,
    )

    assert request.name == 'sft-cleaning'
    assert request.owner_name == 'alice'
    assert request.command == 'dj-process --config recipe.yaml'
    assert request.script_path == str(recipe_path.resolve())
    assert request.execution_spec == DEFAULT_DJ_EXECUTION_SPEC


def test_load_json_arg_accepts_inline_json_and_file(tmp_path: Path) -> None:
    assert _load_json_arg('{"np": 4}') == {'np': 4}

    payload_path = tmp_path / 'params.json'
    payload_path.write_text('{"sampleSize": 10}', encoding='utf-8')

    assert _load_json_arg(str(payload_path)) == {'sampleSize': 10}


def test_load_structured_arg_accepts_yaml_file(tmp_path: Path) -> None:
    payload_path = tmp_path / 'train_spec.yaml'
    payload_path.write_text(
        'name: qwen2-sft-v1\n'
        'command: python train.py --config train.yaml\n'
        'workdir: /tmp/llm-trainer\n',
        encoding='utf-8',
    )

    assert _load_structured_arg(str(payload_path)) == {
        'name': 'qwen2-sft-v1',
        'command': 'python train.py --config train.yaml',
        'workdir': '/tmp/llm-trainer',
    }


def test_load_processing_run_spec_expands_local_recipe_file(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'process.yaml'
    recipe_path.write_text(
        'project_name: loop-demo\n'
        'dataset_path: /data/raw.jsonl\n'
        'export_path: /data/clean.jsonl\n',
        encoding='utf-8',
    )
    spec_path = tmp_path / 'submit.yaml'
    spec_path.write_text(
        'kind: processing\n'
        'name: loop-demo-run\n'
        'process:\n'
        '  dj_configs:\n'
        '    mode: local_file\n'
        f'    path: {recipe_path}\n'
        '  extra_configs:\n'
        '    export_path: /data/final.jsonl\n',
        encoding='utf-8',
    )

    spec = _load_processing_run_spec(str(spec_path))

    assert spec.kind == 'processing'
    assert spec.process.dj_configs.mode == 'local_file'
    assert spec.process.dj_configs.path == str(recipe_path.resolve())
    assert spec.process.dj_configs.recipe_body['project_name'] == 'loop-demo'
    assert spec.process.extra_configs == {'export_path': '/data/final.jsonl'}


def test_load_processing_run_spec_preserves_dataset_references(tmp_path: Path) -> None:
    recipe_path = tmp_path / 'process.yaml'
    recipe_path.write_text(
        'project_name: loop-demo\n'
        'export_path: /data/clean.jsonl\n',
        encoding='utf-8',
    )
    spec_path = tmp_path / 'submit.yaml'
    spec_path.write_text(
        'kind: processing\n'
        'name: loop-demo-run\n'
        'process:\n'
        '  dj_configs:\n'
        '    mode: local_file\n'
        f'    path: {recipe_path}\n'
        '  datasets:\n'
        '    inputs:\n'
        '      - namespace: llm-team.datasets\n'
        '        name: raw_sft\n',
        encoding='utf-8',
    )

    spec = _load_processing_run_spec(str(spec_path))

    assert spec.process.datasets is not None
    assert len(spec.process.datasets.inputs) == 1
    assert spec.process.datasets.inputs[0].namespace == 'llm-team.datasets'
    assert spec.process.datasets.inputs[0].name == 'raw_sft'


def test_load_env_overrides_merges_file_and_inline_values(tmp_path: Path) -> None:
    env_path = tmp_path / 'train.env'
    env_path.write_text(
        'MLFLOW_TRACKING_URI=http://127.0.0.1:5000\n'
        'MLFLOW_EXPERIMENT_NAME=qwen2-sft\n',
        encoding='utf-8',
    )

    assert _load_env_overrides(
        ['MLFLOW_EXPERIMENT_NAME=qwen2-sft-v2', 'CUDA_VISIBLE_DEVICES=0'],
        [str(env_path)],
    ) == {
        'MLFLOW_TRACKING_URI': 'http://127.0.0.1:5000',
        'MLFLOW_EXPERIMENT_NAME': 'qwen2-sft-v2',
        'CUDA_VISIBLE_DEVICES': '0',
    }


def test_normalize_base_url_accepts_common_localhost_forms() -> None:
    assert _normalize_base_url('http:localhost:8000') == 'http://localhost:8000'
    assert _normalize_base_url('localhost:8000') == 'http://localhost:8000'
    assert _normalize_base_url('http://127.0.0.1:8000/') == 'http://127.0.0.1:8000'


def test_render_recipe_list_uses_table_output(capsys: pytest.CaptureFixture[str]) -> None:
    _render_recipe_list(
        {
            'recipes': [
                {
                    'name': 'lineage_base',
                    'ownerName': 'alice',
                    'createdAt': '2026-04-26T10:00:00Z',
                    'currentVersion': {
                        'versionNumber': 2,
                    },
                }
            ]
        }
    )

    output = capsys.readouterr().out
    assert 'RECIPE' in output
    assert 'lineage_base' in output


def test_dump_recipe_yaml_preserves_yaml_shape() -> None:
    recipe_yaml = _dump_recipe_yaml(
        {
            'name': 'lineage_base',
            'currentVersion': {
                'recipeBody': {
                    'project_name': 'loop-demo',
                    'dataset': {'configs': [{'type': 'local', 'path': '/data/raw.jsonl'}]},
                    'np': 4,
                }
            },
        }
    )

    assert 'project_name: loop-demo' in recipe_yaml
    assert 'dataset:' in recipe_yaml
    assert 'configs:' in recipe_yaml
    assert 'np: 4' in recipe_yaml


def test_render_recipe_prints_current_recipe_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    _render_recipe(
        {
            'name': 'lineage_base',
            'currentVersion': {
                'recipeBody': {
                    'project_name': 'loop-demo',
                    'export_path': '/data/out.jsonl',
                }
            },
        }
    )

    output = capsys.readouterr().out
    assert 'project_name: loop-demo' in output
    assert 'export_path: /data/out.jsonl' in output


def test_recipe_download_writes_current_recipe_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recipe_payload = {
        'id': 'recipe-1',
        'name': 'lineage_base',
        'currentVersion': {
            'recipeBody': {
                'project_name': 'loop-demo',
                'export_path': '/data/out.jsonl',
            }
        },
    }

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return recipe_payload

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, path: str):
            assert path == '/api/v1/recipes/recipe-1'
            return _FakeResponse()

    monkeypatch.setattr(cli_commands, 'load_cli_config', lambda: {})
    monkeypatch.setattr(cli_commands, 'resolve_base_url', lambda args, config: 'http://127.0.0.1:8000')
    monkeypatch.setattr(cli_commands, 'client', lambda base_url: _FakeClient())

    output_path = tmp_path / 'downloaded.yaml'
    cli_commands.RecipeCommands().download(
        argparse.Namespace(
            base_url=None,
            recipe_id='recipe-1',
            workspace=None,
            recipe=None,
            output=str(output_path),
            json=False,
        )
    )

    assert output_path.exists()
    assert 'project_name: loop-demo' in output_path.read_text(encoding='utf-8')
    assert str(output_path.resolve()) in capsys.readouterr().out


def test_emit_config_show_uses_human_readable_output(capsys: pytest.CaptureFixture[str]) -> None:
    _render_config({'workspace': 'llm-team', 'user': 'alice', 'base_url': 'http://127.0.0.1:8000'})

    output = capsys.readouterr().out
    assert 'Workspace' in output
    assert 'llm-team' in output
    assert 'alice' in output


def test_run_submit_help_is_available(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'run', 'submit', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '--kind' in output
    assert '--spec' in output
    assert '--parameters' in output
    assert '--env' in output
    assert '--env-file' in output


def test_recipe_download_help_is_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'recipe', 'download', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '--recipe-id' in output
    assert '--recipe' in output
    assert '--output' in output


def test_run_lifecycle_help_is_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'run', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert 'submit' in output
    assert 'list' in output
    assert 'show' in output
    assert 'resume' in output
    assert 'cancel' in output
    assert 'logs' in output


def test_run_cancel_help_is_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'run', 'cancel', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert 'usage: dj-panel run cancel' in output
    assert 'submission_id' in output
    assert '--base-url' in output


def test_recipe_list_and_show_help_are_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'recipe', 'list', '--help'])
    with pytest.raises(SystemExit) as list_exc:
        main()
    assert list_exc.value.code == 0
    assert '--workspace' in capsys.readouterr().out

    monkeypatch.setattr('sys.argv', ['dj-panel', 'recipe', 'show', '--help'])
    with pytest.raises(SystemExit) as show_exc:
        main()
    assert show_exc.value.code == 0
    show_output = capsys.readouterr().out
    assert '--recipe-id' in show_output
    assert '--recipe' in show_output


def test_workspace_cli_help_exposes_member_commands(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'workspace', 'members', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert 'add' in output
    assert 'list' in output


def test_config_cli_help_is_available(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'config', 'set', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '--workspace' in output
    assert '--user' in output
    assert '--base-url' in output


def test_web_cli_help_is_available(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'web', '--help'])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert '--backend-url' in output
    assert '--web-dir' in output
    assert '--npm-bin' in output
    assert '--install-deps' in output


def test_worker_train_and_eval_help_are_available(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from dj_panel.cli import main

    monkeypatch.setattr('sys.argv', ['dj-panel', 'worker', 'train', '--help'])
    with pytest.raises(SystemExit) as train_exc:
        main()
    assert train_exc.value.code == 0
    train_output = capsys.readouterr().out
    assert '--worker-id' in train_output
    assert '--poll-interval' in train_output

    monkeypatch.setattr('sys.argv', ['dj-panel', 'worker', 'eval', '--help'])
    with pytest.raises(SystemExit) as eval_exc:
        main()
    assert eval_exc.value.code == 0
    eval_output = capsys.readouterr().out
    assert '--worker-id' in eval_output
