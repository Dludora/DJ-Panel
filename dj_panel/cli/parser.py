from __future__ import annotations

import argparse
from pathlib import Path

from dj_panel.app.config import get_settings
from dj_panel.app.execution.definitions import DEFAULT_DJ_BIN, WorkerMode
from dj_panel.app.models.constant import RunSubmissionKind
from dj_panel.cli.executor import CliExecutor
from dj_panel.cli.utils import DEFAULT_DJ_COMMAND


def add_json_output_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")


def add_base_url_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=None)


def add_recipe_common_args(parser: argparse.ArgumentParser) -> None:
    settings = get_settings()
    parser.add_argument(
        "file", type=Path, help="Path to a Data-Juicer recipe YAML file"
    )
    add_base_url_flag(parser)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--owner", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument(
        "--command", dest="recipe_command_line", default=DEFAULT_DJ_COMMAND
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=settings.recipe_timeout_seconds
    )
    parser.add_argument(
        "--extra-execution-spec",
        default=None,
        help="JSON object merged into executionSpec",
    )
    add_json_output_flag(parser)


def add_worker_args(parser: argparse.ArgumentParser) -> None:
    settings = get_settings()
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--display-name", default=None)
    parser.add_argument(
        "--workdir",
        type=Path,
        default=settings.worker_workdir_path,
    )
    parser.add_argument("--dj-bin", default=settings.dj_bin or DEFAULT_DJ_BIN)
    parser.add_argument(
        "--poll-interval",
        "--interval-seconds",
        dest="poll_interval",
        type=int,
        default=settings.worker_poll_interval_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="dj-panel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    master = subparsers.add_parser("master", help="Run the DJ Panel backend server")
    master.add_argument("--host", default=settings.api_host)
    master.add_argument("--port", type=int, default=settings.api_port)
    master.add_argument("--database-url", default=settings.database_url)
    master.add_argument(
        "--migrate", action="store_true", help="Run Alembic migrations before starting"
    )
    master.add_argument(
        "--reload", action="store_true", help="Enable uvicorn reload for development"
    )
    master.set_defaults(command_key="master")

    web = subparsers.add_parser("web", help="Run the DJ Panel web development server")
    web.add_argument("--backend-url", dest="base_url", default=None)
    web.add_argument("--host", default=settings.web_host)
    web.add_argument("--port", type=int, default=settings.web_port)
    web.add_argument("--web-dir", default=str(settings.web_dir_path))
    web.add_argument("--npm-bin", default=settings.npm_bin)
    web.add_argument(
        "--install-deps",
        action="store_true",
        help="Install web dependencies before starting",
    )
    web.add_argument(
        "--open",
        action=argparse.BooleanOptionalAction,
        default=settings.web_open,
        help="Open a browser window when starting the web dev server",
    )
    web.set_defaults(command_key="web")

    config = subparsers.add_parser("config", help="Manage local CLI defaults")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_set = config_sub.add_parser(
        "set", help="Set default workspace, user, or base URL"
    )
    config_set.add_argument("--workspace", default=None)
    config_set.add_argument("--user", default=None)
    config_set.add_argument("--base-url", default=None)
    add_json_output_flag(config_set)
    config_set.set_defaults(command_key="config.set")
    config_show = config_sub.add_parser("show", help="Show local CLI defaults")
    add_json_output_flag(config_show)
    config_show.set_defaults(command_key="config.show")

    workspace = subparsers.add_parser("workspace", help="Manage workspaces and members")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_create = workspace_sub.add_parser("create", help="Create a workspace")
    workspace_create.add_argument("slug")
    add_base_url_flag(workspace_create)
    workspace_create.add_argument("--name", default=None)
    workspace_create.add_argument("--description", default="")
    workspace_create.add_argument("--owner", default=None)
    workspace_create.add_argument(
        "--use", action="store_true", help="Store this workspace as the local default"
    )
    add_json_output_flag(workspace_create)
    workspace_create.set_defaults(command_key="workspace.create")
    workspace_list = workspace_sub.add_parser("list", help="List workspaces")
    add_base_url_flag(workspace_list)
    add_json_output_flag(workspace_list)
    workspace_list.set_defaults(command_key="workspace.list")
    workspace_members = workspace_sub.add_parser(
        "members", help="Manage workspace members"
    )
    members_sub = workspace_members.add_subparsers(dest="member_command", required=True)
    members_add = members_sub.add_parser("add", help="Add or update a workspace member")
    add_base_url_flag(members_add)
    members_add.add_argument("--workspace", default=None)
    members_add.add_argument("--user", required=True)
    members_add.add_argument(
        "--role", default="MEMBER", choices=["OWNER", "MAINTAINER", "MEMBER", "VIEWER"]
    )
    add_json_output_flag(members_add)
    members_add.set_defaults(command_key="workspace.members.add")
    members_list = members_sub.add_parser("list", help="List workspace members")
    add_base_url_flag(members_list)
    members_list.add_argument("--workspace", default=None)
    add_json_output_flag(members_list)
    members_list.set_defaults(command_key="workspace.members.list")

    recipe = subparsers.add_parser(
        "recipe", help="Import, inspect, and publish Data-Juicer recipes"
    )
    recipe_sub = recipe.add_subparsers(dest="recipe_command", required=True)
    recipe_import = recipe_sub.add_parser(
        "import", help="Create a new recipe from a YAML file"
    )
    add_recipe_common_args(recipe_import)
    recipe_import.add_argument("--name", default=None)
    recipe_import.set_defaults(command_key="recipe.import")
    recipe_list = recipe_sub.add_parser("list", help="List recipes in a workspace")
    add_base_url_flag(recipe_list)
    recipe_list.add_argument("--workspace", default=None)
    add_json_output_flag(recipe_list)
    recipe_list.set_defaults(command_key="recipe.list")
    recipe_show = recipe_sub.add_parser(
        "show", help="Show a recipe by id or by workspace/name"
    )
    add_base_url_flag(recipe_show)
    recipe_show.add_argument("--recipe-id", default=None)
    recipe_show.add_argument("--workspace", default=None)
    recipe_show.add_argument("--recipe", default=None)
    add_json_output_flag(recipe_show)
    recipe_show.set_defaults(command_key="recipe.show")
    recipe_download = recipe_sub.add_parser(
        "download", help="Download the current recipe body as YAML"
    )
    add_base_url_flag(recipe_download)
    recipe_download.add_argument("--recipe-id", default=None)
    recipe_download.add_argument("--workspace", default=None)
    recipe_download.add_argument("--recipe", default=None)
    recipe_download.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output YAML path; defaults to <recipe-name>.yaml in the current directory",
    )
    add_json_output_flag(recipe_download)
    recipe_download.set_defaults(command_key="recipe.download")
    recipe_publish = recipe_sub.add_parser(
        "publish", help="Publish a new version of an existing recipe"
    )
    add_recipe_common_args(recipe_publish)
    recipe_publish.add_argument("--recipe", required=True, help="Existing recipe name")
    recipe_publish.set_defaults(command_key="recipe.publish")

    run = subparsers.add_parser("run", help="Manage run submissions and execution lifecycle")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    run_submit = run_sub.add_parser("submit", help="Create a run submission")
    add_base_url_flag(run_submit)
    run_submit.add_argument("--workspace", default=None)
    run_submit.add_argument(
        "--kind",
        default=RunSubmissionKind.PROCESSING.value,
        choices=[kind.value for kind in RunSubmissionKind],
    )
    run_submit.add_argument("--requested-by", default=None)
    run_submit.add_argument(
        "--parameters",
        default=None,
        help="JSON object or path to a JSON file used for command-based training/evaluation parameters",
    )
    run_submit.add_argument(
        "--spec",
        default=None,
        help="YAML/JSON object or file describing the processing/training/evaluation submission spec",
    )
    run_submit.add_argument("--name", default=None)
    run_submit.add_argument(
        "--env",
        action="append",
        default=[],
        help="Extra environment variable in KEY=VALUE form; may be passed multiple times",
    )
    run_submit.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Path to an env file (.env, .json, .yaml, .yml); may be passed multiple times",
    )
    add_json_output_flag(run_submit)
    run_submit.set_defaults(command_key="run.submit")

    run_list = run_sub.add_parser("list", help="List run submissions in a workspace")
    add_base_url_flag(run_list)
    run_list.add_argument("--workspace", default=None)
    add_json_output_flag(run_list)
    run_list.set_defaults(command_key="run.list")

    run_show = run_sub.add_parser("show", help="Show a run submission")
    add_base_url_flag(run_show)
    run_show.add_argument("submission_id")
    add_json_output_flag(run_show)
    run_show.set_defaults(command_key="run.show")

    run_resume = run_sub.add_parser(
        "resume", help="Resume a failed or cancelled run submission"
    )
    add_base_url_flag(run_resume)
    run_resume.add_argument("submission_id")
    add_json_output_flag(run_resume)
    run_resume.set_defaults(command_key="run.resume")

    run_cancel = run_sub.add_parser("cancel", help="Cancel a pending run submission")
    add_base_url_flag(run_cancel)
    run_cancel.add_argument("submission_id")
    add_json_output_flag(run_cancel)
    run_cancel.set_defaults(command_key="run.cancel")

    run_logs = run_sub.add_parser("logs", help="Show run logs (reserved)")
    add_base_url_flag(run_logs)
    run_logs.add_argument("submission_id")
    run_logs.set_defaults(command_key="run.logs")

    dataset = subparsers.add_parser("dataset", help="Register datasets and dataset versions")
    dataset_sub = dataset.add_subparsers(dest="dataset_command", required=True)
    dataset_register = dataset_sub.add_parser(
        "register", help="Register a dataset in the catalog"
    )
    add_base_url_flag(dataset_register)
    dataset_register.add_argument("--namespace", required=True)
    dataset_register.add_argument("--name", required=True)
    dataset_register.add_argument("--description", default="")
    dataset_register.add_argument(
        "--facets",
        default=None,
        help="YAML/JSON object or file describing dataset facets",
    )
    dataset_register.add_argument(
        "--dj-input-config",
        default=None,
        help="YAML/JSON object or file used as facets.datajuicerInput.inputConfig",
    )
    add_json_output_flag(dataset_register)
    dataset_register.set_defaults(command_key="dataset.register")

    dataset_list = dataset_sub.add_parser("list", help="List registered datasets")
    add_base_url_flag(dataset_list)
    dataset_list.add_argument("--namespace", default=None)
    dataset_list.add_argument("--limit", type=int, default=100)
    add_json_output_flag(dataset_list)
    dataset_list.set_defaults(command_key="dataset.list")

    dataset_version_register = dataset_sub.add_parser(
        "version-register", help="Register a dataset version"
    )
    add_base_url_flag(dataset_version_register)
    dataset_version_register.add_argument("--namespace", required=True)
    dataset_version_register.add_argument("--name", required=True)
    dataset_version_register.add_argument("--version", required=True)
    dataset_version_register.add_argument("--storage-uri", default=None)
    dataset_version_register.add_argument(
        "--fields",
        default=None,
        help="YAML/JSON list or object containing a 'fields' list",
    )
    dataset_version_register.add_argument(
        "--facets",
        default=None,
        help="YAML/JSON object or file describing version facets",
    )
    dataset_version_register.add_argument("--lifecycle-state", default="ACTIVE")
    add_json_output_flag(dataset_version_register)
    dataset_version_register.set_defaults(command_key="dataset.version-register")

    dataset_show_latest_version = dataset_sub.add_parser(
        "show",
        help="Show the latest dataset version fields and key facets",
    )
    add_base_url_flag(dataset_show_latest_version)
    dataset_show_latest_version.add_argument("--namespace", required=True)
    dataset_show_latest_version.add_argument("--name", required=True)
    add_json_output_flag(dataset_show_latest_version)
    dataset_show_latest_version.set_defaults(command_key="dataset.show")

    dataset_rename = dataset_sub.add_parser("rename", help="Rename a dataset")
    add_base_url_flag(dataset_rename)
    dataset_rename.add_argument("--namespace", required=True)
    dataset_rename.add_argument("--name", required=True)
    dataset_rename.add_argument("--new-name", required=True)
    add_json_output_flag(dataset_rename)
    dataset_rename.set_defaults(command_key="dataset.rename")

    worker = subparsers.add_parser("worker", help="Run task execution workers")
    worker_sub = worker.add_subparsers(dest="worker_kind", required=True)
    worker_dj = worker_sub.add_parser("dj", help="Run a Data-Juicer worker")
    add_worker_args(worker_dj)
    worker_dj.set_defaults(worker_mode=WorkerMode.DJ.value)
    worker_dj.set_defaults(command_key="worker.dj")
    worker_train = worker_sub.add_parser("train", help="Run a training command worker")
    add_worker_args(worker_train)
    worker_train.set_defaults(worker_mode=WorkerMode.TRAIN.value)
    worker_train.set_defaults(command_key="worker.train")
    worker_eval = worker_sub.add_parser("eval", help="Run an evaluation command worker")
    add_worker_args(worker_eval)
    worker_eval.set_defaults(worker_mode=WorkerMode.EVAL.value)
    worker_eval.set_defaults(command_key="worker.eval")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    CliExecutor().execute(parser, args)
