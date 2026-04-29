from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml


DJ_TASK_KIND = 'dj_recipe'
TRAIN_TASK_KIND = 'training'
EVAL_TASK_KIND = 'evaluation'


def console(message: str) -> None:
    print(f'[dj-panel worker] {message}', flush=True)


def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip('/'), timeout=30.0)


def register_worker(
    http: httpx.Client,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    dj_bin: str,
    workdir: Path,
) -> None:
    http.post(
        f'/api/v1/workspaces/{workspace}/workers/register',
        json={
            'workerId': worker_id,
            'displayName': display_name,
            'labels': {
                'host': os.uname().nodename,
                'workerType': 'datajuicer',
            },
            'capabilities': {
                'execution': 'datajuicer',
                'taskKinds': [DJ_TASK_KIND],
                'djBin': dj_bin,
                'workdir': str(workdir),
            },
            'maxConcurrency': 1,
        },
    ).raise_for_status()


def heartbeat(http: httpx.Client, worker_id: str, *, dj_bin: str, workdir: Path) -> None:
    http.post(
        f'/api/v1/workers/{worker_id}/heartbeat',
        json={
            'status': 'ACTIVE',
            'labels': {'workerType': 'datajuicer'},
            'capabilities': {
                'execution': 'datajuicer',
                'taskKinds': [DJ_TASK_KIND],
                'djBin': dj_bin,
                'workdir': str(workdir),
            },
        },
    ).raise_for_status()


def claim_task(http: httpx.Client, workspace: str, worker_id: str) -> Optional[dict[str, Any]]:
    return claim_task_for_kinds(http, workspace, worker_id, [DJ_TASK_KIND])


def claim_task_for_kinds(
    http: httpx.Client, workspace: str, worker_id: str, task_kinds: list[str]
) -> Optional[dict[str, Any]]:
    response = http.post(
        f'/api/v1/workspaces/{workspace}/tasks/claim',
        json={'workerId': worker_id, 'supportedTaskKinds': task_kinds},
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get('task') if payload.get('claimed') else None


def post_transition(http: httpx.Client, task_id: str, suffix: str, body: dict[str, Any]) -> None:
    http.post(f'/api/v1/tasks/{task_id}/{suffix}', json=body).raise_for_status()


def post_log(http: httpx.Client, attempt_id: str, stream: str, message: str, sequence: int) -> int:
    http.post(
        f'/api/v1/task-attempts/{attempt_id}/logs',
        json={'stream': stream, 'message': message, 'sequence': sequence},
    ).raise_for_status()
    return sequence + 1


def post_artifact(
    http: httpx.Client,
    attempt_id: str,
    *,
    kind: str,
    name: str,
    uri: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    http.post(
        f'/api/v1/task-attempts/{attempt_id}/artifacts',
        json={
            'kind': kind,
            'name': name,
            'uri': uri,
            'metadata': metadata or {},
        },
    ).raise_for_status()


def materialize_recipe(task: dict[str, Any], task_dir: Path) -> Path:
    recipe_version = task['recipeVersion']
    recipe_body = dict(recipe_version.get('recipeBody') or {})
    parameters = dict((task.get('submission') or {}).get('parameters') or {})
    recipe_body.update(parameters)

    task_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = task_dir / 'recipe.yaml'
    recipe_path.write_text(
        yaml.safe_dump(recipe_body, sort_keys=False, allow_unicode=False),
        encoding='utf-8',
    )
    return recipe_path


def datajuicer_command(dj_bin: str, recipe_path: Path, execution_spec: dict[str, Any]) -> list[str]:
    config_arg = execution_spec.get('configArg', '--config')
    extra_args = execution_spec.get('extraArgs') or []
    return [dj_bin, config_arg, str(recipe_path), *[str(item) for item in extra_args]]


def task_env(base_url: str, task: dict[str, Any]) -> dict[str, str]:
    env_vars = {k: str(v) for k, v in (task.get('envVars') or {}).items()}
    return {
        **os.environ,
        'OPENLINEAGE_URL': f"{base_url.rstrip('/')}/api/v1/lineage",
        **env_vars,
    }


def run_datajuicer_task(
    http: httpx.Client,
    *,
    base_url: str,
    task: dict[str, Any],
    workdir: Path,
    dj_bin: str,
) -> None:
    task_id = task['taskId']
    attempt_id = task['attemptId']
    lease_token = task['leaseToken']
    execution_spec = task.get('executionSpec') or {}
    task_dir = workdir / 'tasks' / task_id
    recipe_path = materialize_recipe(task, task_dir)
    command = datajuicer_command(dj_bin, recipe_path, execution_spec)
    env = task_env(base_url, task)
    sequence = 0
    console(f'claimed task={task_id} attempt={attempt_id}')
    console(f'materialized recipe={recipe_path}')

    post_transition(
        http,
        task_id,
        'start',
        {
            'attemptId': attempt_id,
            'leaseToken': lease_token,
        },
    )
    post_artifact(
        http,
        attempt_id,
        kind='CONFIG',
        name='materialized-recipe',
        uri=recipe_path.resolve().as_uri(),
        metadata={'taskKind': DJ_TASK_KIND},
    )
    sequence = post_log(http, attempt_id, 'SYSTEM', f"running: {' '.join(command)}", sequence)
    console(f"running {' '.join(command)}")

    try:
        process = subprocess.Popen(
            command,
            cwd=str(task_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sequence = post_log(http, attempt_id, 'STDOUT', line.rstrip('\n'), sequence)
        return_code = process.wait(timeout=task['timeoutSeconds'])
    except subprocess.TimeoutExpired:
        process.kill()
        post_log(http, attempt_id, 'STDERR', 'Data-Juicer task timed out', sequence)
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': 'Data-Juicer task timed out',
            },
        )
        console(f'task timed out task={task_id}')
        return
    except Exception as exc:
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': str(exc),
            },
        )
        raise

    if return_code == 0:
        post_transition(
            http,
            task_id,
            'complete',
            {'attemptId': attempt_id, 'leaseToken': lease_token},
        )
        console(f'task succeeded task={task_id}')
    else:
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': f'Data-Juicer exited with {return_code}',
            },
        )
        console(f'task failed task={task_id} exit_code={return_code}')


def run_once(
    base_url: str,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    workdir: Path,
    dj_bin: str,
) -> bool:
    with client(base_url) as http:
        register_worker(http, workspace, worker_id, display_name, dj_bin=dj_bin, workdir=workdir)
        heartbeat(http, worker_id, dj_bin=dj_bin, workdir=workdir)
        task = claim_task(http, workspace, worker_id)
        if not task:
            console(f'no {DJ_TASK_KIND} task available workspace={workspace}')
            return False
        run_datajuicer_task(http, base_url=base_url, task=task, workdir=workdir, dj_bin=dj_bin)
        return True


def register_command_worker(
    http: httpx.Client,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    worker_type: str,
    task_kind: str,
    workdir: Path,
) -> None:
    http.post(
        f'/api/v1/workspaces/{workspace}/workers/register',
        json={
            'workerId': worker_id,
            'displayName': display_name,
            'labels': {
                'host': os.uname().nodename,
                'workerType': worker_type,
            },
            'capabilities': {
                'execution': 'command',
                'taskKinds': [task_kind],
                'workdir': str(workdir),
            },
            'maxConcurrency': 1,
        },
    ).raise_for_status()


def command_worker_heartbeat(
    http: httpx.Client,
    worker_id: str,
    *,
    worker_type: str,
    task_kind: str,
    workdir: Path,
) -> None:
    http.post(
        f'/api/v1/workers/{worker_id}/heartbeat',
        json={
            'status': 'ACTIVE',
            'labels': {'workerType': worker_type},
            'capabilities': {
                'execution': 'command',
                'taskKinds': [task_kind],
                'workdir': str(workdir),
            },
        },
    ).raise_for_status()


def command_task_workdir(task: dict[str, Any], fallback_workdir: Path) -> Path:
    execution_spec = task.get('executionSpec') or {}
    raw_workdir = execution_spec.get('workdir')
    if raw_workdir:
        return Path(str(raw_workdir)).expanduser()
    return fallback_workdir


def run_command_task(
    http: httpx.Client,
    *,
    task: dict[str, Any],
    fallback_workdir: Path,
) -> None:
    task_id = task['taskId']
    attempt_id = task['attemptId']
    lease_token = task['leaseToken']
    workdir = command_task_workdir(task, fallback_workdir)
    command = str(task['command'])
    env = {**os.environ, **{k: str(v) for k, v in (task.get('envVars') or {}).items()}}
    sequence = 0
    console(f'claimed task={task_id} attempt={attempt_id} workdir={workdir}')

    post_transition(
        http,
        task_id,
        'start',
        {
            'attemptId': attempt_id,
            'leaseToken': lease_token,
        },
    )
    sequence = post_log(http, attempt_id, 'SYSTEM', f'running: {command}', sequence)
    console(f'running {command}')

    try:
        process = subprocess.Popen(
            command,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            shell=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sequence = post_log(http, attempt_id, 'STDOUT', line.rstrip('\n'), sequence)
        return_code = process.wait(timeout=task['timeoutSeconds'])
    except subprocess.TimeoutExpired:
        process.kill()
        post_log(http, attempt_id, 'STDERR', 'Command task timed out', sequence)
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': 'Command task timed out',
            },
        )
        console(f'task timed out task={task_id}')
        return
    except Exception as exc:
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': str(exc),
            },
        )
        raise

    if return_code == 0:
        post_transition(
            http,
            task_id,
            'complete',
            {'attemptId': attempt_id, 'leaseToken': lease_token},
        )
        console(f'task succeeded task={task_id}')
    else:
        post_transition(
            http,
            task_id,
            'fail',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'failureReason': f'Command exited with {return_code}',
            },
        )
        console(f'task failed task={task_id} exit_code={return_code}')


def run_command_once(
    base_url: str,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    worker_type: str,
    task_kind: str,
    workdir: Path,
) -> bool:
    with client(base_url) as http:
        register_command_worker(
            http,
            workspace,
            worker_id,
            display_name,
            worker_type=worker_type,
            task_kind=task_kind,
            workdir=workdir,
        )
        command_worker_heartbeat(
            http,
            worker_id,
            worker_type=worker_type,
            task_kind=task_kind,
            workdir=workdir,
        )
        task = claim_task_for_kinds(http, workspace, worker_id, [task_kind])
        if not task:
            console(f'no {task_kind} task available workspace={workspace}')
            return False
        run_command_task(http, task=task, fallback_workdir=workdir)
        return True


def add_worker_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--base-url', default=None)
    parser.add_argument('--workspace', default=None)
    parser.add_argument('--worker-id', required=True)
    parser.add_argument('--display-name', default=None)
    parser.add_argument('--workdir', type=Path, default=Path(os.getenv('DJ_PANEL_WORKDIR', '/tmp/dj-panel-worker')))
    parser.add_argument('--dj-bin', default=os.getenv('DJ_PANEL_DJ_BIN', 'dj-process'))
    parser.add_argument('--poll-interval', '--interval-seconds', dest='poll_interval', type=int, default=0)


def run_worker_from_args(args: argparse.Namespace) -> None:
    display_name = args.display_name or args.worker_id
    args.workdir.mkdir(parents=True, exist_ok=True)
    worker_mode = getattr(args, 'worker_mode', 'dj')
    console(
        f'starting mode={worker_mode} worker={args.worker_id} workspace={args.workspace} '
        f'base_url={args.base_url} workdir={args.workdir}'
    )
    if worker_mode in {'train', 'eval'}:
        task_kind = TRAIN_TASK_KIND if worker_mode == 'train' else EVAL_TASK_KIND
        if args.poll_interval <= 0:
            run_command_once(
                args.base_url,
                args.workspace,
                args.worker_id,
                display_name,
                worker_type=worker_mode,
                task_kind=task_kind,
                workdir=args.workdir,
            )
            return
        while True:
            run_command_once(
                args.base_url,
                args.workspace,
                args.worker_id,
                display_name,
                worker_type=worker_mode,
                task_kind=task_kind,
                workdir=args.workdir,
            )
            console(f'sleeping {args.poll_interval}s')
            time.sleep(args.poll_interval)
        return
    if args.poll_interval <= 0:
        run_once(
            args.base_url,
            args.workspace,
            args.worker_id,
            display_name,
            workdir=args.workdir,
            dj_bin=args.dj_bin,
        )
        return

    while True:
        run_once(
            args.base_url,
            args.workspace,
            args.worker_id,
            display_name,
            workdir=args.workdir,
            dj_bin=args.dj_bin,
        )
        console(f'sleeping {args.poll_interval}s')
        time.sleep(args.poll_interval)
