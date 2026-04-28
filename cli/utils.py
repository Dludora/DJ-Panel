from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx
import yaml


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DJ_COMMAND = "dj-process --config recipe.yaml"
CONFIG_PATH = Path.home() / ".config" / "dj-panel" / "config.json"


def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=normalize_base_url(base_url), timeout=30.0)


def load_cli_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def save_cli_config(payload: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def normalize_base_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise ValueError("base URL cannot be empty")
    if url.startswith("http:") and not url.startswith("http://"):
        url = "http://" + url.removeprefix("http:")
    elif url.startswith("https:") and not url.startswith("https://"):
        url = "https://" + url.removeprefix("https:")
    elif "://" not in url:
        url = f"http://{url}"

    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise ValueError(
            f"invalid base URL {raw_url!r}; expected something like http://localhost:8000"
        )
    return str(parsed).rstrip("/")


def resolve_base_url(args: argparse.Namespace, config: dict[str, Any]) -> str:
    raw_url = getattr(args, "base_url", None) or config.get("base_url") or DEFAULT_BASE_URL
    return normalize_base_url(raw_url)


def resolve_workspace(
    args: argparse.Namespace, config: dict[str, Any], *, required: bool = True
) -> str | None:
    workspace = getattr(args, "workspace", None) or config.get("workspace")
    if required and not workspace:
        raise ValueError(
            "workspace is required; pass --workspace or set a default with dj-panel config set --workspace <slug>"
        )
    return workspace


def resolve_user(
    args: argparse.Namespace,
    config: dict[str, Any],
    *,
    attr: str = "user",
    required: bool = True,
) -> str | None:
    user = getattr(args, attr, None) or config.get("user") or os.getenv("USER")
    if required and not user:
        raise ValueError(
            f'{attr} is required; pass --{attr.replace("_", "-")} or set a default with dj-panel config set --user <name>'
        )
    return user


def load_json_arg(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    path = Path(raw).expanduser()
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON value must be an object")
    return payload


def load_recipe_body(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("recipe file must contain a YAML mapping at the top level")
    return payload


def default_recipe_name(path: Path, recipe_body: dict[str, Any]) -> str:
    project_name = recipe_body.get("project_name")
    if isinstance(project_name, str) and project_name:
        return project_name
    return path.stem


def recipe_payload(
    *,
    file: Path,
    name: str | None,
    description: str,
    owner: str,
    recipe_command_line: str,
    timeout_seconds: int,
    extra_execution_spec: str | None,
) -> dict[str, Any]:
    recipe_body = load_recipe_body(file.expanduser())
    recipe_path = file.expanduser().resolve()
    execution_spec = {
        "taskKind": "dj_recipe",
        "executor": "dj-process",
        "configMode": "materialize_local_config",
    }
    if extra_execution_spec:
        execution_spec.update(json.loads(extra_execution_spec))
    resolved_name = name or default_recipe_name(recipe_path, recipe_body)
    return {
        "name": resolved_name,
        "description": description,
        "ownerName": owner,
        "recipeBody": recipe_body,
        "command": recipe_command_line,
        "scriptPath": str(recipe_path),
        "parameterSchema": {},
        "envTemplate": {},
        "executionSpec": execution_spec,
        "timeoutSeconds": timeout_seconds,
    }


def find_recipe_by_name(
    client: httpx.Client, workspace: str, recipe_name: str
) -> dict[str, Any]:
    response = client.get(f"/api/v1/workspaces/{workspace}/recipes")
    response.raise_for_status()
    for recipe in response.json().get("recipes", []):
        if recipe.get("name") == recipe_name:
            return recipe
    raise ValueError(f"recipe not found in workspace {workspace!r}: {recipe_name}")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def print_kv(rows: list[tuple[str, Any]]) -> None:
    visible_rows = [
        (label, stringify(value))
        for label, value in rows
        if value not in (None, "", [], {})
    ]
    if not visible_rows:
        print("(empty)")
        return
    width = max(len(label) for label, _ in visible_rows)
    for label, value in visible_rows:
        print(f"{label.ljust(width)}  {value}")


def print_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("(empty)")
        return
    widths: list[int] = []
    for key, label in columns:
        cell_width = max(len(stringify(row.get(key, ""))) for row in rows)
        widths.append(max(len(label), cell_width))
    header = "  ".join(label.ljust(width) for (_, label), width in zip(columns, widths))
    divider = "  ".join("-" * width for width in widths)
    print(header)
    print(divider)
    for row in rows:
        print(
            "  ".join(
                stringify(row.get(key, "")).ljust(width)
                for (key, _), width in zip(columns, widths)
            )
        )


def render_json(payload: Any) -> None:
    print_json(payload)


def render_config(payload: dict[str, Any]) -> None:
    print_kv(
        [
            ("Workspace", payload.get("workspace")),
            ("User", payload.get("user")),
            ("Base URL", payload.get("base_url")),
        ]
    )


def render_workspace(payload: dict[str, Any]) -> None:
    print_kv(
        [
            ("Workspace", payload.get("slug")),
            ("Name", payload.get("name")),
            ("Description", payload.get("description")),
            ("Created", payload.get("createdAt")),
            ("Updated", payload.get("updatedAt")),
        ]
    )


def render_workspaces(payload: dict[str, Any]) -> None:
    print_table(
        payload.get("workspaces", []),
        [("slug", "WORKSPACE"), ("name", "NAME"), ("description", "DESCRIPTION")],
    )


def render_member(payload: dict[str, Any]) -> None:
    print_kv(
        [
            ("User", payload.get("userName")),
            ("Role", payload.get("role")),
            ("Created", payload.get("createdAt")),
            ("Updated", payload.get("updatedAt")),
        ]
    )


def render_members(payload: dict[str, Any]) -> None:
    print_table(
        payload.get("members", []),
        [("userName", "USER"), ("role", "ROLE"), ("createdAt", "CREATED")],
    )


def render_recipe_list(payload: dict[str, Any]) -> None:
    rows = []
    for recipe in payload.get("recipes", []):
        current = recipe.get("currentVersion") or {}
        rows.append(
            {
                "name": recipe.get("name"),
                "ownerName": recipe.get("ownerName"),
                "versionNumber": current.get("versionNumber", ""),
                "createdAt": recipe.get("createdAt", ""),
            }
        )
    print_table(
        rows,
        [
            ("name", "RECIPE"),
            ("ownerName", "OWNER"),
            ("versionNumber", "VERSION"),
            ("createdAt", "CREATED"),
        ],
    )


def render_recipe(payload: dict[str, Any]) -> None:
    current = payload.get("currentVersion") or {}
    print_kv(
        [
            ("Recipe", payload.get("name")),
            ("Recipe ID", payload.get("id")),
            ("Workspace ID", payload.get("workspaceId")),
            ("Owner", payload.get("ownerName")),
            ("Description", payload.get("description")),
            ("Current Version", current.get("versionNumber")),
            ("Current Version ID", current.get("id")),
            ("Created", payload.get("createdAt")),
            ("Updated", payload.get("updatedAt")),
        ]
    )


def render_recipe_version(payload: dict[str, Any]) -> None:
    print_kv(
        [
            ("Recipe Version ID", payload.get("id")),
            ("Version", payload.get("versionNumber")),
            ("Created By", payload.get("createdBy")),
            ("Command", payload.get("command")),
            ("Script Path", payload.get("scriptPath")),
            ("Timeout Seconds", payload.get("timeoutSeconds")),
            ("Execution Spec", payload.get("executionSpec")),
            ("Recipe Body", payload.get("recipeBody")),
            ("Created", payload.get("createdAt")),
        ]
    )


def render_submission(payload: dict[str, Any]) -> None:
    print_kv(
        [
            ("Submission ID", payload.get("id")),
            ("Workspace ID", payload.get("workspaceId")),
            ("Recipe ID", payload.get("recipeId")),
            ("Recipe Version ID", payload.get("recipeVersionId")),
            ("Status", payload.get("status")),
            ("Requested By", payload.get("requestedBy")),
            ("Parameters", payload.get("parameters")),
            ("Inputs", payload.get("inputs")),
            ("Outputs", payload.get("outputs")),
            ("Created", payload.get("createdAt")),
            ("Updated", payload.get("updatedAt")),
        ]
    )


def render_submissions(payload: dict[str, Any]) -> None:
    print_table(
        payload.get("submissions", []),
        [
            ("id", "ID"),
            ("recipeId", "RECIPE ID"),
            ("status", "STATUS"),
            ("requestedBy", "REQUESTED BY"),
            ("createdAt", "CREATED"),
        ],
    )


def emit(payload: dict[str, Any], *, json_output: bool = False) -> None:
    if json_output:
        render_json(payload)
    else:
        render_json(payload)
