from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from dj_panel.app.config import get_settings
from dj_panel.app.execution.worker_runtime import run_worker_from_args
from dj_panel.app.models.api import (
    AssetCreateRequest,
    AssetVersionCreateRequest,
    RunSubmissionCreateRequest,
    WorkspaceCreateRequest,
    WorkspaceMemberAddRequest,
)
from dj_panel.app.models.constant import AssetKind, RunSubmissionKind
from dj_panel.cli.utils import (
    build_recipe_create_request,
    build_recipe_version_request,
    client,
    find_recipe_by_name,
    load_cli_config,
    load_env_overrides,
    load_json_arg,
    load_processing_run_spec,
    load_structured_arg,
    render_config,
    render_dataset,
    render_dataset_latest_version,
    render_dataset_list,
    render_dataset_version,
    render_json,
    render_member,
    render_members,
    render_recipe,
    render_recipe_list,
    render_recipe_version,
    render_submission,
    render_submissions,
    render_workspace,
    render_workspaces,
    normalize_base_url,
    resolve_base_url,
    resolve_user,
    run_submission_kind,
    resolve_workspace,
    save_cli_config,
)


def render(payload: dict, *, json_output: bool, human_renderer) -> None:
    if json_output:
        render_json(payload)
    else:
        human_renderer(payload)


def cmd_master(args: argparse.Namespace) -> None:
    import uvicorn
    from alembic import command
    from alembic.config import Config

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if args.migrate:
        config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        command.upgrade(Config(str(config_path)), "head")
    uvicorn.run("dj_panel.app.main:app", host=args.host, port=args.port, reload=args.reload)


def cmd_web(args: argparse.Namespace) -> None:
    settings = get_settings()
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    web_dir = Path(args.web_dir).expanduser() if args.web_dir else settings.web_dir_path
    if not web_dir.exists():
        raise ValueError(
            f"web directory not found: {web_dir}. Pass --web-dir or set DJ_PANEL_WEB_DIR."
        )
    if not (web_dir / "package.json").exists():
        raise ValueError(f"package.json not found in web directory: {web_dir}")
    npm_bin = shutil.which(args.npm_bin)
    if not npm_bin:
        raise ValueError(f"npm executable not found: {args.npm_bin}")

    env = os.environ.copy()
    env["DJ_PANEL_API_ORIGIN"] = base_url
    env["DJ_PANEL_WEB_HOST"] = args.host
    env["DJ_PANEL_WEB_PORT"] = str(args.port)
    env["DJ_PANEL_WEB_OPEN"] = "1" if args.open else "0"
    if args.install_deps or not (web_dir / "node_modules").exists():
        install_command = [npm_bin, "install"]
        subprocess.run(install_command, cwd=web_dir, env=env, check=True)
    subprocess.run([npm_bin, "run", "dev"], cwd=web_dir, env=env, check=True)


def cmd_config_set(args: argparse.Namespace) -> None:
    payload = load_cli_config()
    if args.workspace is not None:
        payload["workspace"] = args.workspace
    if args.user is not None:
        payload["user"] = args.user
    if args.base_url is not None:
        payload["base_url"] = normalize_base_url(args.base_url)
    save_cli_config(payload)
    render(payload, json_output=args.json, human_renderer=render_config)


def cmd_config_show(args: argparse.Namespace) -> None:
    render(load_cli_config(), json_output=args.json, human_renderer=render_config)


def cmd_workspace_create(args: argparse.Namespace) -> None:
    config = load_cli_config()
    owner = resolve_user(args, config, attr="owner")
    base_url = resolve_base_url(args, config)
    payload = WorkspaceCreateRequest(
        slug=args.slug,
        name=args.name or args.slug,
        description=args.description,
        ownerName=owner,
    ).model_dump(by_alias=True, exclude_none=True)
    with client(base_url) as http:
        response = http.post("/api/v1/workspaces", json=payload)
        response.raise_for_status()
        result = response.json()
    if args.use:
        config["workspace"] = result["slug"]
        if owner:
            config["user"] = owner
        config["base_url"] = base_url
        save_cli_config(config)
    render(result, json_output=args.json, human_renderer=render_workspace)


def cmd_workspace_list(args: argparse.Namespace) -> None:
    base_url = resolve_base_url(args, load_cli_config())
    with client(base_url) as http:
        response = http.get("/api/v1/workspaces")
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_workspaces)


def cmd_workspace_members_add(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    payload = WorkspaceMemberAddRequest(userName=args.user, role=args.role).model_dump(
        by_alias=True, exclude_none=True
    )
    with client(base_url) as http:
        response = http.post(f"/api/v1/workspaces/{workspace}/members", json=payload)
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_member)


def cmd_workspace_members_list(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    with client(base_url) as http:
        response = http.get(f"/api/v1/workspaces/{workspace}/members")
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_members)


def cmd_recipe_import(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    owner = resolve_user(args, config, attr="owner")
    payload = build_recipe_create_request(
        file=args.file,
        name=args.name,
        description=args.description,
        owner=owner,
        recipe_command_line=args.recipe_command_line,
        timeout_seconds=args.timeout_seconds,
        extra_execution_spec=args.extra_execution_spec,
    ).model_dump(by_alias=True, exclude_none=True)
    with client(base_url) as http:
        response = http.post(f"/api/v1/workspaces/{workspace}/recipes", json=payload)
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_recipe)


def cmd_recipe_list(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    with client(base_url) as http:
        response = http.get(f"/api/v1/workspaces/{workspace}/recipes")
        response.raise_for_status()
        render(
            response.json(), json_output=args.json, human_renderer=render_recipe_list
        )


def cmd_recipe_show(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        if args.recipe_id:
            response = http.get(f"/api/v1/recipes/{args.recipe_id}")
            response.raise_for_status()
            render(response.json(), json_output=args.json, human_renderer=render_recipe)
            return
        workspace = resolve_workspace(args, config)
        if not args.recipe:
            raise ValueError("recipe show requires --recipe or --recipe-id")
        render(
            find_recipe_by_name(http, workspace, args.recipe),
            json_output=args.json,
            human_renderer=render_recipe,
        )


def cmd_recipe_publish(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    owner = resolve_user(args, config, attr="owner")
    version_payload = build_recipe_version_request(
        file=args.file,
        description=args.description,
        owner=owner,
        recipe_command_line=args.recipe_command_line,
        timeout_seconds=args.timeout_seconds,
        extra_execution_spec=args.extra_execution_spec,
    ).model_dump(by_alias=True, exclude_none=True)
    with client(base_url) as http:
        recipe = find_recipe_by_name(http, workspace, args.recipe)
        response = http.post(
            f"/api/v1/recipes/{recipe['id']}/versions", json=version_payload
        )
        response.raise_for_status()
        render(
            response.json(), json_output=args.json, human_renderer=render_recipe_version
        )


def cmd_run_submit(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    requested_by = resolve_user(args, config, attr="requested_by")
    env_overrides = load_env_overrides(args.env, args.env_file)
    submission_kind = run_submission_kind(args.kind)
    with client(base_url) as http:
        if submission_kind == RunSubmissionKind.PROCESSING:
            processing_spec = load_processing_run_spec(args.spec)
            spec_payload = processing_spec.to_api_dict()
            process_payload = dict(spec_payload.get("process") or {})
            process_env = dict(process_payload.get("env") or {})
            payload = RunSubmissionCreateRequest(
                submissionKind=submission_kind,
                name=args.name or processing_spec.name,
                requestedBy=requested_by or processing_spec.requested_by or "",
                parameters=dict(processing_spec.process.extra_configs or {}),
                spec={
                    **spec_payload,
                    "process": {
                        **process_payload,
                        "env": {**process_env, **env_overrides},
                    },
                },
                inputs=[],
                outputs=[],
            ).model_dump(by_alias=True, exclude_none=True)
        else:
            parameters = load_json_arg(args.parameters)
            spec = load_structured_arg(args.spec)
            if not spec:
                raise ValueError("training/evaluation run submit requires --spec")
            spec_env = dict(spec.get("env") or {})
            if env_overrides:
                spec["env"] = {**spec_env, **env_overrides}
            payload = RunSubmissionCreateRequest(
                submissionKind=submission_kind,
                name=args.name or spec.get("name"),
                requestedBy=requested_by,
                parameters=parameters,
                spec=spec,
                inputs=spec.get("inputs", []),
                outputs=spec.get("outputs", []),
            ).model_dump(by_alias=True, exclude_none=True)
        response = http.post(
            f"/api/v1/workspaces/{workspace}/run-submissions", json=payload
        )
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_submission)


def cmd_run_list(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    workspace = resolve_workspace(args, config)
    with client(base_url) as http:
        response = http.get(f"/api/v1/workspaces/{workspace}/run-submissions")
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_submissions)


def cmd_run_show(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        response = http.get(f"/api/v1/run-submissions/{args.submission_id}")
        response.raise_for_status()
        render(
            response.json()["submission"],
            json_output=args.json,
            human_renderer=render_submission,
        )


def cmd_run_resume(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        response = http.post(f"/api/v1/run-submissions/{args.submission_id}/resume")
        response.raise_for_status()
        render(
            response.json()["submission"],
            json_output=args.json,
            human_renderer=render_submission,
        )


def cmd_run_cancel(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        response = http.post(f"/api/v1/run-submissions/{args.submission_id}/cancel")
        response.raise_for_status()
        render(
            response.json()["submission"],
            json_output=args.json,
            human_renderer=render_submission,
        )


def cmd_run_logs(args: argparse.Namespace) -> None:
    raise ValueError("run logs is reserved but not implemented yet")


def cmd_dataset_register(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    facets = load_structured_arg(args.facets)
    if args.dj_input_config:
        facets["datajuicerInput"] = {
            **(
                facets.get("datajuicerInput", {})
                if isinstance(facets.get("datajuicerInput"), dict)
                else {}
            ),
            "inputConfig": load_structured_arg(args.dj_input_config),
        }
    payload = AssetCreateRequest(
        namespace=args.namespace,
        name=args.name,
        assetKind=AssetKind.DATASET,
        description=args.description,
        facets=facets,
    ).model_dump(by_alias=True, exclude_none=True)
    with client(base_url) as http:
        response = http.post("/api/v1/assets", json=payload)
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_dataset)


def cmd_dataset_version_register(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    fields_payload = load_structured_arg(args.fields)
    facets_payload = load_structured_arg(args.facets)
    if fields_payload and not isinstance(fields_payload.get("fields", fields_payload), list):
        raise ValueError("fields payload must be a list or an object containing a 'fields' list")
    fields = fields_payload.get("fields", fields_payload) if fields_payload else []
    if not isinstance(fields, list):
        raise ValueError("fields payload must resolve to a list")
    with client(base_url) as http:
        asset = http.get(
            f"/api/v1/namespaces/{args.namespace}/datasets/{args.name}"
        )
        asset.raise_for_status()
        asset_id = asset.json()["catalogId"]
        payload = AssetVersionCreateRequest(
            version=args.version,
            storageUri=args.storage_uri,
            fields=fields,
            facets=facets_payload,
            lifecycleState=args.lifecycle_state,
        ).model_dump(by_alias=True, exclude_none=True)
        response = http.post(f"/api/v1/assets/{asset_id}/versions", json=payload)
        response.raise_for_status()
        render(
            response.json(),
            json_output=args.json,
            human_renderer=render_dataset_version,
        )


def cmd_dataset_list(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    limit = min(args.limit, 100)
    offset = 0
    datasets: list[dict] = []
    total_count = 0
    with client(base_url) as http:
        while True:
            response = http.get(
                "/api/v1/assets",
                params={
                    "namespace": args.namespace,
                    "assetKind": AssetKind.DATASET.value,
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()
            payload = response.json()
            items = [
                item
                for item in payload.get("assets", [])
                if not str(item.get("namespace", "")).startswith("inmemory://")
            ]
            datasets.extend(items)
            total_count += len(items)
            if offset + limit >= payload.get("totalCount", 0):
                break
            offset += limit
    render(
        {"datasets": datasets, "totalCount": total_count},
        json_output=args.json,
        human_renderer=render_dataset_list,
    )


def cmd_dataset_show_latest_version(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        dataset_response = http.get(
            f"/api/v1/namespaces/{args.namespace}/datasets/{args.name}"
        )
        dataset_response.raise_for_status()
        dataset_payload = dataset_response.json()

        response = http.get(
            f"/api/v1/namespaces/{args.namespace}/datasets/{args.name}/versions",
            params={"limit": 1, "offset": 0},
        )
        response.raise_for_status()
        payload = response.json()
        versions = payload.get("versions", [])
        if not versions:
            raise ValueError("dataset version not found")
        merged = dict(versions[0])
        merged["facets"] = {
            **(dataset_payload.get("facets") or {}),
            **(versions[0].get("facets") or {}),
        }
        render(
            merged,
            json_output=args.json,
            human_renderer=render_dataset_latest_version,
        )


def cmd_dataset_rename(args: argparse.Namespace) -> None:
    config = load_cli_config()
    base_url = resolve_base_url(args, config)
    with client(base_url) as http:
        asset = http.get(
            f"/api/v1/namespaces/{args.namespace}/datasets/{args.name}"
        )
        asset.raise_for_status()
        asset_id = asset.json()["catalogId"]
        response = http.patch(
            f"/api/v1/assets/{asset_id}",
            json={"name": args.new_name},
        )
        response.raise_for_status()
        render(response.json(), json_output=args.json, human_renderer=render_dataset)


def cmd_worker_dj(args: argparse.Namespace) -> None:
    config = load_cli_config()
    args.base_url = resolve_base_url(args, config)
    args.workspace = resolve_workspace(args, config)
    run_worker_from_args(args)


def cmd_worker_train(args: argparse.Namespace) -> None:
    config = load_cli_config()
    args.base_url = resolve_base_url(args, config)
    args.workspace = resolve_workspace(args, config)
    run_worker_from_args(args)


def cmd_worker_eval(args: argparse.Namespace) -> None:
    config = load_cli_config()
    args.base_url = resolve_base_url(args, config)
    args.workspace = resolve_workspace(args, config)
    run_worker_from_args(args)
