from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
import yaml

from dj_panel.app.execution.worker_api import post_artifact, post_transition
from dj_panel.app.models.api import TaskClaimPayload
from dj_panel.app.models.constant import ArtifactKind


def materialize_recipe(task: TaskClaimPayload, task_dir: Path) -> Path:
    if task.recipe_version is not None:
        recipe_body = dict(task.recipe_version.recipe_body or {})
    else:
        recipe_body = dict((task.execution_spec or {}).get("recipeBody") or {})
    if not recipe_body:
        raise ValueError("Data-Juicer task missing materializable recipe body")

    parameters = dict((task.submission or {}).get("parameters") or {})
    recipe_body.update(parameters)
    # Give DJ an absolute work_dir template whose final resolved value is the
    # same task dir after {job_id} substitution.
    recipe_body["work_dir"] = str(task_dir.parent / "{job_id}")

    task_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = task_dir / "recipe.yaml"
    recipe_path.write_text(
        yaml.safe_dump(recipe_body, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return recipe_path


def datajuicer_command(
    dj_bin: str, recipe_path: Path, execution_spec: dict[str, Any], job_id: str
) -> list[str]:
    config_arg = execution_spec.get("configArg", "--config")
    extra_args = execution_spec.get("extraArgs") or []
    return [
        dj_bin,
        config_arg,
        str(recipe_path.resolve()),
        "--job_id",
        job_id,
        *[str(item) for item in extra_args],
    ]


def task_env(base_url: str, task: TaskClaimPayload) -> dict[str, str]:
    env_vars = {k: str(v) for k, v in task.env_vars.items()}
    return {
        **os.environ,
        "OPENLINEAGE_URL": f"{base_url.rstrip('/')}/api/v1/lineage",
        **env_vars,
    }


def command_task_workdir(task: TaskClaimPayload, fallback_workdir: Path) -> Path:
    execution_spec = task.execution_spec or {}
    raw_workdir = execution_spec.get("workdir")
    if raw_workdir:
        return Path(str(raw_workdir)).expanduser()
    return fallback_workdir


def task_runtime_dir(root_workdir: Path, task_id: str) -> Path:
    runtime_dir = root_workdir.resolve() / "tasks" / task_id
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def run_log_path(runtime_dir: Path) -> Path:
    return runtime_dir / "run.log"


def record_log_artifact(
    http: httpx.Client,
    *,
    attempt_id: str,
    task_kind: str,
    log_path: Path,
) -> None:
    if not log_path.exists():
        return
    post_artifact(
        http,
        attempt_id,
        kind=ArtifactKind.LOG.value,
        name="run.log",
        uri=log_path.resolve().as_uri(),
        metadata={"taskKind": task_kind, "stream": "COMBINED"},
    )


def run_datajuicer_task(
    http: httpx.Client,
    *,
    console,
    base_url: str,
    task: TaskClaimPayload,
    workdir: Path,
    dj_bin: str,
    task_kind: str,
) -> None:
    task_id = task.task_id
    attempt_id = task.attempt_id
    lease_token = task.lease_token
    execution_spec = task.execution_spec or {}
    task_dir = task_runtime_dir(workdir, task_id)
    recipe_path = materialize_recipe(task, task_dir)
    log_path = run_log_path(task_dir)
    command = datajuicer_command(dj_bin, recipe_path, execution_spec, task_id)
    env = task_env(base_url, task)
    console(f"claimed task={task_id} attempt={attempt_id}")
    console(f"materialized recipe={recipe_path}")
    console(f"log path={log_path}")

    post_transition(
        http,
        task_id,
        "start",
        {
            "attemptId": attempt_id,
            "leaseToken": lease_token,
        },
    )
    post_artifact(
        http,
        attempt_id,
        kind="CONFIG",
        name="materialized-recipe",
        uri=recipe_path.resolve().as_uri(),
        metadata={"taskKind": task_kind},
    )
    console(f"running {' '.join(command)}")

    process: subprocess.Popen[str] | None = None
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"$ {' '.join(command)}\n")
            log_file.flush()
            process = subprocess.Popen(
                command,
                cwd=str(task_dir),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            return_code = process.wait(timeout=task.timeout_seconds)
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n[dj-panel] Data-Juicer task timed out\n")
        record_log_artifact(
            http, attempt_id=attempt_id, task_kind=task_kind, log_path=log_path
        )
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": "Data-Juicer task timed out",
            },
        )
        console(f"task timed out task={task_id} log={log_path}")
        return
    except Exception as exc:
        if log_path.exists():
            record_log_artifact(
                http, attempt_id=attempt_id, task_kind=task_kind, log_path=log_path
            )
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": str(exc),
            },
        )
        console(f"task error task={task_id} log={log_path}")
        raise

    record_log_artifact(http, attempt_id=attempt_id, task_kind=task_kind, log_path=log_path)
    if return_code == 0:
        post_transition(
            http,
            task_id,
            "complete",
            {"attemptId": attempt_id, "leaseToken": lease_token},
        )
        console(f"task succeeded task={task_id}")
    else:
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": f"Data-Juicer exited with {return_code}",
            },
        )
        console(f"task failed task={task_id} exit_code={return_code} log={log_path}")


def run_command_task(
    http: httpx.Client,
    *,
    console,
    base_url: str,
    task: TaskClaimPayload,
    fallback_workdir: Path,
) -> None:
    task_id = task.task_id
    attempt_id = task.attempt_id
    lease_token = task.lease_token
    runtime_dir = task_runtime_dir(fallback_workdir, task_id)
    log_path = run_log_path(runtime_dir)
    workdir = command_task_workdir(task, fallback_workdir)
    command = str(task.command)
    env = task_env(base_url, task)
    console(f"claimed task={task_id} attempt={attempt_id} workdir={workdir}")

    post_transition(
        http,
        task_id,
        "start",
        {
            "attemptId": attempt_id,
            "leaseToken": lease_token,
        },
    )
    console(f"running {command}")

    process: subprocess.Popen[str] | None = None
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"$ {command}\n")
            log_file.flush()
            process = subprocess.Popen(
                command,
                cwd=str(workdir),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                shell=True,
            )
            return_code = process.wait(timeout=task.timeout_seconds)
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n[dj-panel] Command task timed out\n")
        record_log_artifact(
            http, attempt_id=attempt_id, task_kind=task.task_kind.value, log_path=log_path
        )
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": "Command task timed out",
            },
        )
        console(f"task timed out task={task_id}")
        return
    except Exception as exc:
        if log_path.exists():
            record_log_artifact(
                http,
                attempt_id=attempt_id,
                task_kind=task.task_kind.value,
                log_path=log_path,
            )
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": str(exc),
            },
        )
        raise

    record_log_artifact(
        http, attempt_id=attempt_id, task_kind=task.task_kind.value, log_path=log_path
    )
    if return_code == 0:
        post_transition(
            http,
            task_id,
            "complete",
            {"attemptId": attempt_id, "leaseToken": lease_token},
        )
        console(f"task succeeded task={task_id}")
    else:
        post_transition(
            http,
            task_id,
            "fail",
            {
                "attemptId": attempt_id,
                "leaseToken": lease_token,
                "failureReason": f"Command exited with {return_code}",
            },
        )
        console(f"task failed task={task_id} exit_code={return_code}")
