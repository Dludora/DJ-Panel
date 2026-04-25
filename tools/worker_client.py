from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx


def _client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip('/'), timeout=30.0)


def register_worker(client: httpx.Client, workspace: str, worker_id: str, display_name: str) -> None:
    client.post(
        f'/api/v1/workspaces/{workspace}/workers/register',
        json={
            'workerId': worker_id,
            'displayName': display_name,
            'labels': {'host': os.uname().nodename},
            'capabilities': {'execution': 'local-shell'},
            'maxConcurrency': 1,
        },
    ).raise_for_status()


def heartbeat(client: httpx.Client, worker_id: str) -> None:
    client.post(
        f'/api/v1/workers/{worker_id}/heartbeat',
        json={'status': 'ACTIVE', 'labels': {}, 'capabilities': {'execution': 'local-shell'}},
    ).raise_for_status()


def claim_task(client: httpx.Client, workspace: str, worker_id: str) -> Optional[dict]:
    response = client.post(
        f'/api/v1/workspaces/{workspace}/tasks/claim',
        json={'workerId': worker_id},
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get('task') if payload.get('claimed') else None


def post_transition(client: httpx.Client, task_id: str, suffix: str, body: dict) -> None:
    client.post(f'/api/v1/tasks/{task_id}/{suffix}', json=body).raise_for_status()


def post_log(client: httpx.Client, attempt_id: str, stream: str, message: str, sequence: int) -> None:
    client.post(
        f'/api/v1/task-attempts/{attempt_id}/logs',
        json={'stream': stream, 'message': message, 'sequence': sequence},
    ).raise_for_status()


def run_once(base_url: str, workspace: str, worker_id: str, display_name: str) -> bool:
    with _client(base_url) as client:
        register_worker(client, workspace, worker_id, display_name)
        heartbeat(client, worker_id)
        task = claim_task(client, workspace, worker_id)
        if not task:
            return False

        task_id = task['taskId']
        attempt_id = task['attemptId']
        lease_token = task['leaseToken']
        command = task['command']
        env = {**os.environ, **{k: str(v) for k, v in task['envVars'].items()}}

        post_transition(
            client,
            task_id,
            'start',
            {
                'attemptId': attempt_id,
                'leaseToken': lease_token,
                'rootLineageNodeId': task['recipeVersion'].get('lineageJobName'),
            },
        )

        process = subprocess.Popen(
            command,
            shell=True,
            cwd=str(Path(task['recipeVersion']['scriptPath']).expanduser().parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        sequence = 0
        stdout, stderr = process.communicate(timeout=task['timeoutSeconds'])
        for line in stdout.splitlines():
            post_log(client, attempt_id, 'STDOUT', line, sequence)
            sequence += 1
        for line in stderr.splitlines():
            post_log(client, attempt_id, 'STDERR', line, sequence)
            sequence += 1

        if process.returncode == 0:
            post_transition(
                client,
                task_id,
                'complete',
                {'attemptId': attempt_id, 'leaseToken': lease_token},
            )
        else:
            post_transition(
                client,
                task_id,
                'fail',
                {
                    'attemptId': attempt_id,
                    'leaseToken': lease_token,
                    'failureReason': f'command exited with {process.returncode}',
                },
            )
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description='DJ Panel worker client')
    parser.add_argument('--base-url', default=os.getenv('DJ_PANEL_BASE_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--worker-id', required=True)
    parser.add_argument('--display-name', default=None)
    parser.add_argument('--interval-seconds', type=int, default=0)
    args = parser.parse_args()

    display_name = args.display_name or args.worker_id
    if args.interval_seconds <= 0:
        run_once(args.base_url, args.workspace, args.worker_id, display_name)
        return

    while True:
        run_once(args.base_url, args.workspace, args.worker_id, display_name)
        time.sleep(args.interval_seconds)


if __name__ == '__main__':
    main()
