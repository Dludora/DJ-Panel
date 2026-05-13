from __future__ import annotations

import argparse
import time
from pathlib import Path

from dj_panel.app.execution.definitions import (
    DEFAULT_DJ_BIN,
    WorkerMode,
    worker_profile_for_mode,
)
from dj_panel.app.execution.task_runners import run_command_task, run_datajuicer_task
from dj_panel.app.execution.worker_api import (
    claim_task,
    client,
    heartbeat_command_worker,
    heartbeat_dj_worker,
    register_command_worker,
    register_dj_worker,
)


def console(message: str) -> None:
    print(f"[dj-panel worker] {message}", flush=True)


def run_dj_once(
    base_url: str,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    workdir: Path,
    dj_bin: str,
) -> bool:
    profile = worker_profile_for_mode(WorkerMode.DJ)
    with client(base_url) as http:
        register_dj_worker(
            http,
            workspace,
            worker_id,
            display_name,
            dj_bin=dj_bin,
            workdir=workdir,
            task_kind=profile.task_kind,
        )
        heartbeat_dj_worker(
            http,
            worker_id,
            dj_bin=dj_bin,
            workdir=workdir,
            task_kind=profile.task_kind,
        )
        task = claim_task(http, workspace, worker_id, [profile.task_kind])
        if not task:
            console(
                f"no {profile.task_kind.value} task available workspace={workspace}"
            )
            return False
        run_datajuicer_task(
            http,
            console=console,
            base_url=base_url,
            task=task,
            workdir=workdir,
            dj_bin=dj_bin,
            task_kind=profile.task_kind.value,
        )
        return True


def run_command_once(
    base_url: str,
    workspace: str,
    worker_id: str,
    display_name: str,
    *,
    worker_mode: WorkerMode,
    workdir: Path,
) -> bool:
    profile = worker_profile_for_mode(worker_mode)
    with client(base_url) as http:
        register_command_worker(
            http,
            workspace,
            worker_id,
            display_name,
            worker_type=profile.worker_type,
            task_kind=profile.task_kind,
            workdir=workdir,
        )
        heartbeat_command_worker(
            http,
            worker_id,
            worker_type=profile.worker_type,
            task_kind=profile.task_kind,
            workdir=workdir,
        )
        task = claim_task(http, workspace, worker_id, [profile.task_kind])
        if not task:
            console(
                f"no {profile.task_kind.value} task available workspace={workspace}"
            )
            return False
        run_command_task(
            http,
            console=console,
            base_url=base_url,
            task=task,
            fallback_workdir=workdir,
        )
        return True


def run_worker_from_args(args: argparse.Namespace) -> None:
    display_name = args.display_name or args.worker_id
    args.workdir = args.workdir.expanduser().resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    worker_mode = WorkerMode(getattr(args, "worker_mode", WorkerMode.DJ.value))
    console(
        f"starting mode={worker_mode.value} worker={args.worker_id} workspace={args.workspace} "
        f"base_url={args.base_url} workdir={args.workdir}"
    )

    if worker_mode == WorkerMode.DJ:
        _run_loop(
            args.poll_interval,
            lambda: run_dj_once(
                args.base_url,
                args.workspace,
                args.worker_id,
                display_name,
                workdir=args.workdir,
                dj_bin=args.dj_bin or DEFAULT_DJ_BIN,
            ),
        )
        return

    _run_loop(
        args.poll_interval,
        lambda: run_command_once(
            args.base_url,
            args.workspace,
            args.worker_id,
            display_name,
            worker_mode=worker_mode,
            workdir=args.workdir,
        ),
    )


def _run_loop(poll_interval: int, run_once) -> None:
    if poll_interval <= 0:
        run_once()
        return

    while True:
        run_once()
        console(f"sleeping {poll_interval}s")
        time.sleep(poll_interval)
