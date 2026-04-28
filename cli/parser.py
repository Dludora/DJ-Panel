from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx

from cli.commands import (
    cmd_config_set,
    cmd_config_show,
    cmd_master,
    cmd_recipe_import,
    cmd_recipe_list,
    cmd_recipe_publish,
    cmd_recipe_show,
    cmd_run_submit,
    cmd_web,
    cmd_worker_dj,
    cmd_workspace_create,
    cmd_workspace_list,
    cmd_workspace_members_add,
    cmd_workspace_members_list,
)
from cli.utils import DEFAULT_DJ_COMMAND
from cli.worker import add_worker_args


def add_json_output_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--json', action='store_true', help='Print raw JSON output')


def add_base_url_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--base-url', default=None)


def add_recipe_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('file', type=Path, help='Path to a Data-Juicer recipe YAML file')
    add_base_url_flag(parser)
    parser.add_argument('--workspace', default=None)
    parser.add_argument('--owner', default=None)
    parser.add_argument('--description', default='')
    parser.add_argument('--command', dest='recipe_command_line', default=DEFAULT_DJ_COMMAND)
    parser.add_argument('--timeout-seconds', type=int, default=7200)
    parser.add_argument('--extra-execution-spec', default=None, help='JSON object merged into executionSpec')
    add_json_output_flag(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='dj-panel')
    subparsers = parser.add_subparsers(dest='command', required=True)

    master = subparsers.add_parser('master', help='Run the DJ Panel backend server')
    master.add_argument('--host', default=os.getenv('DJ_PANEL_HOST', '127.0.0.1'))
    master.add_argument('--port', type=int, default=int(os.getenv('DJ_PANEL_PORT', '8000')))
    master.add_argument('--database-url', default=os.getenv('DJ_PANEL_DATABASE_URL'))
    master.add_argument('--migrate', action='store_true', help='Run Alembic migrations before starting')
    master.add_argument('--reload', action='store_true', help='Enable uvicorn reload for development')
    master.set_defaults(handler=cmd_master)

    web = subparsers.add_parser('web', help='Run the DJ Panel web development server')
    web.add_argument('--backend-url', dest='base_url', default=None)
    web.add_argument('--host', default=os.getenv('DJ_PANEL_WEB_HOST', '127.0.0.1'))
    web.add_argument('--port', type=int, default=int(os.getenv('DJ_PANEL_WEB_PORT', '1337')))
    web.add_argument('--web-dir', default=os.getenv('DJ_PANEL_WEB_DIR'))
    web.add_argument('--npm-bin', default=os.getenv('DJ_PANEL_NPM_BIN', 'npm'))
    web.add_argument('--install-deps', action='store_true', help='Install web dependencies before starting')
    web.add_argument('--open', action='store_true', help='Open a browser window when starting the web dev server')
    web.set_defaults(handler=cmd_web)

    config = subparsers.add_parser('config', help='Manage local CLI defaults')
    config_sub = config.add_subparsers(dest='config_command', required=True)
    config_set = config_sub.add_parser('set', help='Set default workspace, user, or base URL')
    config_set.add_argument('--workspace', default=None)
    config_set.add_argument('--user', default=None)
    config_set.add_argument('--base-url', default=None)
    add_json_output_flag(config_set)
    config_set.set_defaults(handler=cmd_config_set)
    config_show = config_sub.add_parser('show', help='Show local CLI defaults')
    add_json_output_flag(config_show)
    config_show.set_defaults(handler=cmd_config_show)

    workspace = subparsers.add_parser('workspace', help='Manage workspaces and members')
    workspace_sub = workspace.add_subparsers(dest='workspace_command', required=True)
    workspace_create = workspace_sub.add_parser('create', help='Create a workspace')
    workspace_create.add_argument('slug')
    add_base_url_flag(workspace_create)
    workspace_create.add_argument('--name', default=None)
    workspace_create.add_argument('--description', default='')
    workspace_create.add_argument('--owner', default=None)
    workspace_create.add_argument('--use', action='store_true', help='Store this workspace as the local default')
    add_json_output_flag(workspace_create)
    workspace_create.set_defaults(handler=cmd_workspace_create)
    workspace_list = workspace_sub.add_parser('list', help='List workspaces')
    add_base_url_flag(workspace_list)
    add_json_output_flag(workspace_list)
    workspace_list.set_defaults(handler=cmd_workspace_list)
    workspace_members = workspace_sub.add_parser('members', help='Manage workspace members')
    members_sub = workspace_members.add_subparsers(dest='member_command', required=True)
    members_add = members_sub.add_parser('add', help='Add or update a workspace member')
    add_base_url_flag(members_add)
    members_add.add_argument('--workspace', default=None)
    members_add.add_argument('--user', required=True)
    members_add.add_argument('--role', default='MEMBER', choices=['OWNER', 'MAINTAINER', 'MEMBER', 'VIEWER'])
    add_json_output_flag(members_add)
    members_add.set_defaults(handler=cmd_workspace_members_add)
    members_list = members_sub.add_parser('list', help='List workspace members')
    add_base_url_flag(members_list)
    members_list.add_argument('--workspace', default=None)
    add_json_output_flag(members_list)
    members_list.set_defaults(handler=cmd_workspace_members_list)

    recipe = subparsers.add_parser('recipe', help='Import, inspect, and publish Data-Juicer recipes')
    recipe_sub = recipe.add_subparsers(dest='recipe_command', required=True)
    recipe_import = recipe_sub.add_parser('import', help='Create a new recipe from a YAML file')
    add_recipe_common_args(recipe_import)
    recipe_import.add_argument('--name', default=None)
    recipe_import.set_defaults(handler=cmd_recipe_import)
    recipe_list = recipe_sub.add_parser('list', help='List recipes in a workspace')
    add_base_url_flag(recipe_list)
    recipe_list.add_argument('--workspace', default=None)
    add_json_output_flag(recipe_list)
    recipe_list.set_defaults(handler=cmd_recipe_list)
    recipe_show = recipe_sub.add_parser('show', help='Show a recipe by id or by workspace/name')
    add_base_url_flag(recipe_show)
    recipe_show.add_argument('--recipe-id', default=None)
    recipe_show.add_argument('--workspace', default=None)
    recipe_show.add_argument('--recipe', default=None)
    add_json_output_flag(recipe_show)
    recipe_show.set_defaults(handler=cmd_recipe_show)
    recipe_publish = recipe_sub.add_parser('publish', help='Publish a new version of an existing recipe')
    add_recipe_common_args(recipe_publish)
    recipe_publish.add_argument('--recipe', required=True, help='Existing recipe name')
    recipe_publish.set_defaults(handler=cmd_recipe_publish)

    run = subparsers.add_parser('run', help='Submit processing runs')
    run_sub = run.add_subparsers(dest='run_command', required=True)
    run_submit = run_sub.add_parser('submit', help='Create a processing run submission')
    add_base_url_flag(run_submit)
    run_submit.add_argument('--workspace', default=None)
    run_submit.add_argument('--recipe', default=None, help='Recipe name; uses current version')
    run_submit.add_argument('--recipe-version-id', default=None)
    run_submit.add_argument('--requested-by', default=None)
    run_submit.add_argument('--parameters', default=None, help='JSON object or path to a JSON file merged into the materialized recipe')
    add_json_output_flag(run_submit)
    run_submit.set_defaults(handler=cmd_run_submit)

    worker = subparsers.add_parser('worker', help='Run task execution workers')
    worker_sub = worker.add_subparsers(dest='worker_kind', required=True)
    worker_dj = worker_sub.add_parser('dj', help='Run a Data-Juicer worker')
    add_worker_args(worker_dj)
    worker_dj.set_defaults(handler=cmd_worker_dj)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handler = getattr(args, 'handler', None)
        if handler is None:
            parser.error('no handler configured')
        handler(args)
    except httpx.HTTPStatusError as exc:
        parser.exit(1, f'HTTP {exc.response.status_code}: {exc.response.text}\n')
    except Exception as exc:
        parser.exit(1, f'error: {exc}\n')
