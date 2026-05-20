from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dj_panel.app.config import get_settings
from dj_panel.app.execution.definitions import DEFAULT_DJ_BIN, WorkerMode
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
    DEFAULT_DJ_COMMAND,
    build_recipe_create_request,
    build_recipe_version_request,
    client,
    dump_recipe_yaml,
    find_recipe_by_name,
    load_cli_config,
    load_env_overrides,
    load_json_arg,
    load_processing_run_spec,
    load_structured_arg,
    normalize_base_url,
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
    resolve_base_url,
    resolve_user,
    resolve_workspace,
    run_submission_kind,
    save_cli_config,
)


def render(payload: dict, *, json_output: bool, human_renderer) -> None:
    if json_output:
        render_json(payload)
    else:
        human_renderer(payload)


@dataclass(frozen=True)
class CliOptionSpec:
    flags: tuple[str, ...]
    kwargs: dict[str, Any]


def option(*flags: str, **kwargs: Any):
    spec = CliOptionSpec(tuple(flags), dict(kwargs))

    def decorator(func):
        specs = list(getattr(func, "__cli_options__", []))
        specs.append(spec)
        setattr(func, "__cli_options__", specs)
        entries = list(getattr(func, "__cli_argument_entries__", []))
        entries.append(("option", spec))
        setattr(func, "__cli_argument_entries__", entries)
        return func

    return decorator


def use_options(spec_factory):
    def decorator(func):
        factories = list(getattr(func, "__cli_option_factories__", []))
        factories.append(spec_factory)
        setattr(func, "__cli_option_factories__", factories)
        entries = list(getattr(func, "__cli_argument_entries__", []))
        entries.append(("factory", spec_factory))
        setattr(func, "__cli_argument_entries__", entries)
        return func

    return decorator


def defaults(**kwargs: Any):
    def decorator(func):
        merged = dict(getattr(func, "__cli_defaults__", {}))
        merged.update(kwargs)
        setattr(func, "__cli_defaults__", merged)
        return func

    return decorator


def command(path: str | tuple[str, ...], *, help: str):
    command_path = (path,) if isinstance(path, str) else tuple(path)

    def decorator(func):
        setattr(func, "__cli_command__", {"path": command_path, "help": help})
        return func

    return decorator


def command_group(
    group_id: str,
    *,
    path: str | tuple[str, ...] | None = None,
    help: str,
    subgroup_help: dict[tuple[str, ...], str] | None = None,
):
    group_path = (
        () if path is None else ((path,) if isinstance(path, str) else tuple(path))
    )

    def decorator(cls):
        setattr(
            cls,
            "__cli_group__",
            {
                "id": group_id,
                "path": group_path,
                "help": help,
                "subgroup_help": subgroup_help or {},
            },
        )
        return cls

    return decorator


def json_output_options() -> list[CliOptionSpec]:
    return [
        CliOptionSpec(
            ("--json",), {"action": "store_true", "help": "Print raw JSON output"}
        )
    ]


def base_url_options() -> list[CliOptionSpec]:
    return [CliOptionSpec(("--base-url",), {"default": None})]


def recipe_common_options() -> list[CliOptionSpec]:
    settings = get_settings()
    return [
        CliOptionSpec(
            ("file",), {"type": Path, "help": "Path to a Data-Juicer recipe YAML file"}
        ),
        *base_url_options(),
        CliOptionSpec(("--workspace",), {"default": None}),
        CliOptionSpec(("--owner",), {"default": None}),
        CliOptionSpec(("--description",), {"default": ""}),
        CliOptionSpec(
            ("--command",),
            {"dest": "recipe_command_line", "default": DEFAULT_DJ_COMMAND},
        ),
        CliOptionSpec(
            ("--timeout-seconds",),
            {"type": int, "default": settings.recipe_timeout_seconds},
        ),
        CliOptionSpec(
            ("--extra-execution-spec",),
            {"default": None, "help": "JSON object merged into executionSpec"},
        ),
        *json_output_options(),
    ]


def worker_common_options() -> list[CliOptionSpec]:
    settings = get_settings()
    return [
        *base_url_options(),
        CliOptionSpec(("--workspace",), {"default": None}),
        CliOptionSpec(("--worker-id",), {"required": True}),
        CliOptionSpec(("--display-name",), {"default": None}),
        CliOptionSpec(
            ("--workdir",), {"type": Path, "default": settings.worker_workdir_path}
        ),
        CliOptionSpec(("--dj-bin",), {"default": settings.dj_bin or DEFAULT_DJ_BIN}),
        CliOptionSpec(
            ("--poll-interval", "--interval-seconds"),
            {
                "dest": "poll_interval",
                "type": int,
                "default": settings.worker_poll_interval_seconds,
            },
        ),
    ]


def _iter_command_methods(group_cls: type) -> list[tuple[str, Any]]:
    return [
        (name, value)
        for name, value in group_cls.__dict__.items()
        if getattr(value, "__cli_command__", None) is not None
    ]


def _materialize_option_specs(func) -> list[CliOptionSpec]:
    specs: list[CliOptionSpec] = []
    for entry_kind, entry_value in reversed(
        list(getattr(func, "__cli_argument_entries__", []))
    ):
        if entry_kind == "option":
            specs.append(entry_value)
        elif entry_kind == "factory":
            specs.extend(entry_value())
    return specs


def _subparser_dest(path: tuple[str, ...]) -> str:
    joined = "_".join(path) if path else "root"
    return f"{joined}_command"


def register_command_groups(
    subparsers: argparse._SubParsersAction, group_types: list[type]
) -> None:
    parser_cache: dict[tuple[str, ...], argparse.ArgumentParser] = {}
    subparsers_cache: dict[tuple[str, ...], argparse._SubParsersAction] = {
        (): subparsers
    }

    for group_cls in group_types:
        group_meta = getattr(group_cls, "__cli_group__")
        group_path = tuple(group_meta["path"])
        group_help = group_meta["help"]
        subgroup_help = dict(group_meta.get("subgroup_help") or {})

        def ensure_path(path: tuple[str, ...]) -> None:
            for index in range(1, len(path) + 1):
                current_path = path[:index]
                if current_path in parser_cache:
                    continue
                parent_path = current_path[:-1]
                parent_subparsers = subparsers_cache[parent_path]
                if current_path == group_path:
                    help_text = group_help
                else:
                    relative_path = current_path[len(group_path) :]
                    help_text = subgroup_help.get(relative_path)
                parser = parent_subparsers.add_parser(current_path[-1], help=help_text)
                parser_cache[current_path] = parser
                subparsers_cache[current_path] = parser.add_subparsers(
                    dest=_subparser_dest(current_path), required=True
                )

        if group_path:
            ensure_path(group_path)

        for method_name, func in _iter_command_methods(group_cls):
            command_meta = getattr(func, "__cli_command__")
            full_path = group_path + tuple(command_meta["path"])
            parent_path = full_path[:-1]
            leaf_name = full_path[-1]
            if parent_path:
                ensure_path(parent_path)
            parent_subparsers = subparsers_cache[parent_path]
            leaf_parser = parent_subparsers.add_parser(
                leaf_name, help=command_meta["help"]
            )
            for spec in _materialize_option_specs(func):
                leaf_parser.add_argument(*spec.flags, **spec.kwargs)
            leaf_defaults = dict(getattr(func, "__cli_defaults__", {}))
            leaf_parser.set_defaults(
                handler_group=group_meta["id"],
                handler_method=method_name,
                **leaf_defaults,
            )


class CliContext:
    """Shared CLI execution context for resolved config, identity, and HTTP access."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.settings = get_settings()
        self.config = load_cli_config()

    @property
    def base_url(self) -> str:
        return resolve_base_url(self.args, self.config)

    def workspace(self, *, required: bool = True) -> str | None:
        return resolve_workspace(self.args, self.config, required=required)

    def user(self, *, attr: str = "user", required: bool = True) -> str | None:
        return resolve_user(self.args, self.config, attr=attr, required=required)

    def http_client(self):
        return client(self.base_url)

    def render(self, payload: dict[str, Any], *, human_renderer) -> None:
        render(
            payload,
            json_output=bool(getattr(self.args, "json", False)),
            human_renderer=human_renderer,
        )


@command_group("system", help="System entrypoints")
class SystemCommands:
    @command("master", help="Run the DJ Panel backend server")
    @option("--host", default=get_settings().api_host)
    @option("--port", type=int, default=get_settings().api_port)
    @option("--database-url", default=get_settings().database_url)
    @option(
        "--migrate", action="store_true", help="Run Alembic migrations before starting"
    )
    @option(
        "--reload", action="store_true", help="Enable uvicorn reload for development"
    )
    def master(self, args: argparse.Namespace) -> None:
        import uvicorn
        from alembic import command
        from alembic.config import Config

        if args.database_url:
            os.environ["DATABASE_URL"] = args.database_url
        if args.migrate:
            config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
            command.upgrade(Config(str(config_path)), "head")
        uvicorn.run(
            "dj_panel.app.main:app", host=args.host, port=args.port, reload=args.reload
        )

    @command("web", help="Run the DJ Panel web development server")
    @option("--backend-url", dest="base_url", default=None)
    @option("--host", default=get_settings().web_host)
    @option("--port", type=int, default=get_settings().web_port)
    @option("--web-dir", default=str(get_settings().web_dir_path))
    @option("--npm-bin", default=get_settings().npm_bin)
    @option(
        "--install-deps",
        action="store_true",
        help="Install web dependencies before starting",
    )
    @option(
        "--open",
        action=argparse.BooleanOptionalAction,
        default=get_settings().web_open,
        help="Open a browser window when starting the web dev server",
    )
    def web(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        web_dir = (
            Path(args.web_dir).expanduser()
            if args.web_dir
            else ctx.settings.web_dir_path
        )
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
        env["DJ_PANEL_API_ORIGIN"] = ctx.base_url
        env["DJ_PANEL_WEB_HOST"] = args.host
        env["DJ_PANEL_WEB_PORT"] = str(args.port)
        env["DJ_PANEL_WEB_OPEN"] = "1" if args.open else "0"
        if args.install_deps or not (web_dir / "node_modules").exists():
            subprocess.run([npm_bin, "install"], cwd=web_dir, env=env, check=True)
        subprocess.run([npm_bin, "run", "dev"], cwd=web_dir, env=env, check=True)


@command_group("config", path="config", help="Manage local CLI defaults")
class ConfigCommands:
    @command("set", help="Set default workspace, user, or base URL")
    @option("--workspace", default=None)
    @option("--user", default=None)
    @option("--base-url", default=None)
    @use_options(json_output_options)
    def set(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        payload = dict(ctx.config)
        if args.workspace is not None:
            payload["workspace"] = args.workspace
        if args.user is not None:
            payload["user"] = args.user
        if args.base_url is not None:
            payload["base_url"] = normalize_base_url(args.base_url)
        save_cli_config(payload)
        ctx.render(payload, human_renderer=render_config)

    @command("show", help="Show local CLI defaults")
    @use_options(json_output_options)
    def show(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        ctx.render(ctx.config, human_renderer=render_config)


@command_group(
    "workspace",
    path="workspace",
    help="Manage workspaces and members",
    subgroup_help={("members",): "Manage workspace members"},
)
class WorkspaceCommands:
    @command("create", help="Create a workspace")
    @option("slug")
    @use_options(base_url_options)
    @option("--name", default=None)
    @option("--description", default="")
    @option("--owner", default=None)
    @option(
        "--use", action="store_true", help="Store this workspace as the local default"
    )
    @use_options(json_output_options)
    def create(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        owner = ctx.user(attr="owner")
        payload = WorkspaceCreateRequest(
            slug=args.slug,
            name=args.name or args.slug,
            description=args.description,
            ownerName=owner,
        ).model_dump(by_alias=True, exclude_none=True)
        with ctx.http_client() as http:
            response = http.post("/api/v1/workspaces", json=payload)
            response.raise_for_status()
            result = response.json()
        if args.use:
            payload = dict(ctx.config)
            payload["workspace"] = result["slug"]
            if owner:
                payload["user"] = owner
            payload["base_url"] = ctx.base_url
            save_cli_config(payload)
        ctx.render(result, human_renderer=render_workspace)

    @command("list", help="List workspaces")
    @use_options(base_url_options)
    @use_options(json_output_options)
    def list(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.get("/api/v1/workspaces")
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_workspaces)

    @command(("members", "add"), help="Add or update a workspace member")
    @use_options(base_url_options)
    @option("--workspace", default=None)
    @option("--user", required=True)
    @option(
        "--role", default="MEMBER", choices=["OWNER", "MAINTAINER", "MEMBER", "VIEWER"]
    )
    @use_options(json_output_options)
    def members_add(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        workspace = ctx.workspace()
        payload = WorkspaceMemberAddRequest(
            userName=args.user, role=args.role
        ).model_dump(by_alias=True, exclude_none=True)
        with ctx.http_client() as http:
            response = http.post(
                f"/api/v1/workspaces/{workspace}/members", json=payload
            )
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_member)

    @command(("members", "list"), help="List workspace members")
    @use_options(base_url_options)
    @option("--workspace", default=None)
    @use_options(json_output_options)
    def members_list(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        workspace = ctx.workspace()
        with ctx.http_client() as http:
            response = http.get(f"/api/v1/workspaces/{workspace}/members")
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_members)


@command_group(
    "recipe", path="recipe", help="Import, inspect, and publish Data-Juicer recipes"
)
class RecipeCommands:
    @command("import", help="Create a new recipe from a YAML file")
    @use_options(recipe_common_options)
    @option("--name", default=None)
    def import_recipe(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        payload = build_recipe_create_request(
            file=args.file,
            name=args.name,
            description=args.description,
            owner=ctx.user(attr="owner"),
            recipe_command_line=args.recipe_command_line,
            timeout_seconds=args.timeout_seconds,
            extra_execution_spec=args.extra_execution_spec,
        ).model_dump(by_alias=True, exclude_none=True)
        with ctx.http_client() as http:
            response = http.post(
                f"/api/v1/workspaces/{ctx.workspace()}/recipes", json=payload
            )
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_recipe)

    @command("list", help="List recipes in a workspace")
    @use_options(base_url_options)
    @option("--workspace", default=None)
    @use_options(json_output_options)
    def list(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.get(f"/api/v1/workspaces/{ctx.workspace()}/recipes")
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_recipe_list)

    @command("show", help="Show a recipe by id or by workspace/name")
    @use_options(base_url_options)
    @option("--recipe-id", default=None)
    @option("--workspace", default=None)
    @option("--recipe", default=None)
    @use_options(json_output_options)
    def show(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            recipe = self._load_recipe(args, ctx, http)
            ctx.render(recipe, human_renderer=render_recipe)

    @command("download", help="Download the current recipe body as YAML")
    @use_options(base_url_options)
    @option("--recipe-id", default=None)
    @option("--workspace", default=None)
    @option("--recipe", default=None)
    @option(
        "--output",
        "-o",
        default=None,
        help="Output YAML path; defaults to <recipe-name>.yaml in the current directory",
    )
    @use_options(json_output_options)
    def download(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            recipe = self._load_recipe(args, ctx, http)
        output_path = (
            Path(args.output).expanduser()
            if args.output
            else Path(f"{recipe['name']}.yaml")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dump_recipe_yaml(recipe), encoding="utf-8")
        if args.json:
            render_json(
                {
                    "recipeId": recipe.get("id"),
                    "recipe": recipe.get("name"),
                    "path": str(output_path.resolve()),
                }
            )
        else:
            print(f"Downloaded recipe to {output_path.resolve()}")

    @command("publish", help="Publish a new version of an existing recipe")
    @use_options(recipe_common_options)
    @option("--recipe", required=True, help="Existing recipe name")
    def publish(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        version_payload = build_recipe_version_request(
            file=args.file,
            description=args.description,
            owner=ctx.user(attr="owner"),
            recipe_command_line=args.recipe_command_line,
            timeout_seconds=args.timeout_seconds,
            extra_execution_spec=args.extra_execution_spec,
        ).model_dump(by_alias=True, exclude_none=True)
        with ctx.http_client() as http:
            recipe = find_recipe_by_name(http, ctx.workspace(), args.recipe)
            response = http.post(
                f"/api/v1/recipes/{recipe['id']}/versions", json=version_payload
            )
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_recipe_version)

    @staticmethod
    def _load_recipe(args: argparse.Namespace, ctx: CliContext, http) -> dict[str, Any]:
        if args.recipe_id:
            response = http.get(f"/api/v1/recipes/{args.recipe_id}")
            response.raise_for_status()
            return response.json()
        if not args.recipe:
            raise ValueError("recipe command requires --recipe or --recipe-id")
        return find_recipe_by_name(http, ctx.workspace(), args.recipe)


@command_group("run", path="run", help="Manage run submissions and execution lifecycle")
class RunCommands:
    @command("submit", help="Create a run submission")
    @use_options(base_url_options)
    @option("--workspace", default=None)
    @option(
        "--kind",
        default=RunSubmissionKind.PROCESSING.value,
        choices=[kind.value for kind in RunSubmissionKind],
    )
    @option("--requested-by", default=None)
    @option(
        "--parameters",
        default=None,
        help="JSON object or path to a JSON file used for command-based training/evaluation parameters",
    )
    @option(
        "--spec",
        default=None,
        help="YAML/JSON object or file describing the processing/training/evaluation submission spec",
    )
    @option("--name", default=None)
    @option(
        "--env",
        action="append",
        default=[],
        help="Extra environment variable in KEY=VALUE form; may be passed multiple times",
    )
    @option(
        "--env-file",
        action="append",
        default=[],
        help="Path to an env file (.env, .json, .yaml, .yml); may be passed multiple times",
    )
    @use_options(json_output_options)
    def submit(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        requested_by = ctx.user(attr="requested_by")
        env_overrides = load_env_overrides(args.env, args.env_file)
        submission_kind = run_submission_kind(args.kind)
        with ctx.http_client() as http:
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
                f"/api/v1/workspaces/{ctx.workspace()}/run-submissions", json=payload
            )
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_submission)

    @command("list", help="List run submissions in a workspace")
    @use_options(base_url_options)
    @option("--workspace", default=None)
    @use_options(json_output_options)
    def list(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.get(f"/api/v1/workspaces/{ctx.workspace()}/run-submissions")
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_submissions)

    @command("show", help="Show a run submission")
    @use_options(base_url_options)
    @option("submission_id")
    @use_options(json_output_options)
    def show(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.get(f"/api/v1/run-submissions/{args.submission_id}")
            response.raise_for_status()
            ctx.render(response.json()["submission"], human_renderer=render_submission)

    @command("resume", help="Resume a failed or cancelled run submission")
    @use_options(base_url_options)
    @option("submission_id")
    @use_options(json_output_options)
    def resume(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.post(f"/api/v1/run-submissions/{args.submission_id}/resume")
            response.raise_for_status()
            ctx.render(response.json()["submission"], human_renderer=render_submission)

    @command("cancel", help="Cancel a pending run submission")
    @use_options(base_url_options)
    @option("submission_id")
    @use_options(json_output_options)
    def cancel(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            response = http.post(f"/api/v1/run-submissions/{args.submission_id}/cancel")
            response.raise_for_status()
            ctx.render(response.json()["submission"], human_renderer=render_submission)

    @command("logs", help="Show run logs (reserved)")
    @use_options(base_url_options)
    @option("submission_id")
    def logs(self, args: argparse.Namespace) -> None:
        raise ValueError("run logs is reserved but not implemented yet")


@command_group("dataset", path="dataset", help="Register datasets and dataset versions")
class DatasetCommands:
    @command("register", help="Register a dataset in the catalog")
    @use_options(base_url_options)
    @option("--namespace", required=True)
    @option("--name", required=True)
    @option("--description", default="")
    @option(
        "--facets",
        default=None,
        help="YAML/JSON object or file describing dataset facets",
    )
    @option(
        "--dj-input-config",
        default=None,
        help="YAML/JSON object or file used as facets.datajuicerInput.inputConfig",
    )
    @use_options(json_output_options)
    def register(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
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
        with ctx.http_client() as http:
            response = http.post("/api/v1/assets", json=payload)
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_dataset)

    @command("version-register", help="Register a dataset version")
    @use_options(base_url_options)
    @option("--namespace", required=True)
    @option("--name", required=True)
    @option("--version", required=True)
    @option("--storage-uri", default=None)
    @option(
        "--fields",
        default=None,
        help="YAML/JSON list or object containing a 'fields' list",
    )
    @option(
        "--facets",
        default=None,
        help="YAML/JSON object or file describing version facets",
    )
    @option("--lifecycle-state", default="ACTIVE")
    @use_options(json_output_options)
    def version_register(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        fields_payload = load_structured_arg(args.fields)
        facets_payload = load_structured_arg(args.facets)
        if fields_payload and not isinstance(
            fields_payload.get("fields", fields_payload), list
        ):
            raise ValueError(
                "fields payload must be a list or an object containing a 'fields' list"
            )
        fields = fields_payload.get("fields", fields_payload) if fields_payload else []
        if not isinstance(fields, list):
            raise ValueError("fields payload must resolve to a list")
        with ctx.http_client() as http:
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
            ctx.render(response.json(), human_renderer=render_dataset_version)

    @command("list", help="List registered datasets")
    @use_options(base_url_options)
    @option("--namespace", default=None)
    @option("--limit", type=int, default=100)
    @use_options(json_output_options)
    def list(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        limit = min(args.limit, 100)
        offset = 0
        datasets: list[dict[str, Any]] = []
        total_count = 0
        with ctx.http_client() as http:
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
        ctx.render(
            {"datasets": datasets, "totalCount": total_count},
            human_renderer=render_dataset_list,
        )

    @command("show", help="Show the latest dataset version fields and key facets")
    @use_options(base_url_options)
    @option("--namespace", required=True)
    @option("--name", required=True)
    @use_options(json_output_options)
    def show_latest_version(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
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
            ctx.render(merged, human_renderer=render_dataset_latest_version)

    @command("rename", help="Rename a dataset")
    @use_options(base_url_options)
    @option("--namespace", required=True)
    @option("--name", required=True)
    @option("--new-name", required=True)
    @use_options(json_output_options)
    def rename(self, args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        with ctx.http_client() as http:
            asset = http.get(
                f"/api/v1/namespaces/{args.namespace}/datasets/{args.name}"
            )
            asset.raise_for_status()
            asset_id = asset.json()["catalogId"]
            response = http.patch(
                f"/api/v1/assets/{asset_id}", json={"name": args.new_name}
            )
            response.raise_for_status()
            ctx.render(response.json(), human_renderer=render_dataset)


@command_group("worker", path="worker", help="Run task execution workers")
class WorkerCommands:
    @command("dj", help="Run a Data-Juicer worker")
    @use_options(worker_common_options)
    @defaults(worker_mode=WorkerMode.DJ.value)
    def dj(self, args: argparse.Namespace) -> None:
        self._run(args)

    @command("train", help="Run a training command worker")
    @use_options(worker_common_options)
    @defaults(worker_mode=WorkerMode.TRAIN.value)
    def train(self, args: argparse.Namespace) -> None:
        self._run(args)

    @command("eval", help="Run an evaluation command worker")
    @use_options(worker_common_options)
    @defaults(worker_mode=WorkerMode.EVAL.value)
    def eval(self, args: argparse.Namespace) -> None:
        self._run(args)

    @staticmethod
    def _run(args: argparse.Namespace) -> None:
        ctx = CliContext(args)
        args.base_url = ctx.base_url
        args.workspace = ctx.workspace()
        run_worker_from_args(args)


def build_command_groups() -> dict[str, object]:
    """Registry used by the executor to resolve parser-bound command groups."""

    return {
        "system": SystemCommands(),
        "config": ConfigCommands(),
        "workspace": WorkspaceCommands(),
        "recipe": RecipeCommands(),
        "run": RunCommands(),
        "dataset": DatasetCommands(),
        "worker": WorkerCommands(),
    }


COMMAND_GROUP_TYPES = [
    SystemCommands,
    ConfigCommands,
    WorkspaceCommands,
    RecipeCommands,
    RunCommands,
    DatasetCommands,
    WorkerCommands,
]
