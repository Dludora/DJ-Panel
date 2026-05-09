from __future__ import annotations

import argparse
from collections.abc import Callable

import httpx

import cli.commands as commands


CommandHandler = Callable[[argparse.Namespace], None]


class CliExecutor:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {
            "master": commands.cmd_master,
            "web": commands.cmd_web,
            "config.set": commands.cmd_config_set,
            "config.show": commands.cmd_config_show,
            "workspace.create": commands.cmd_workspace_create,
            "workspace.list": commands.cmd_workspace_list,
            "workspace.members.add": commands.cmd_workspace_members_add,
            "workspace.members.list": commands.cmd_workspace_members_list,
            "recipe.import": commands.cmd_recipe_import,
            "recipe.list": commands.cmd_recipe_list,
            "recipe.show": commands.cmd_recipe_show,
            "recipe.publish": commands.cmd_recipe_publish,
            "run.submit": commands.cmd_run_submit,
            "dataset.list": commands.cmd_dataset_list,
            "dataset.register": commands.cmd_dataset_register,
            "dataset.show": commands.cmd_dataset_show_latest_version,
            "dataset.rename": commands.cmd_dataset_rename,
            "dataset.version-register": commands.cmd_dataset_version_register,
            "worker.dj": commands.cmd_worker_dj,
            "worker.train": commands.cmd_worker_train,
            "worker.eval": commands.cmd_worker_eval,
        }

    def execute(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
        command_key = getattr(args, "command_key", None)
        if command_key is None:
            parser.error("no command configured")

        handler = self._handlers.get(command_key)
        if handler is None:
            parser.error(f"unknown command: {command_key}")

        try:
            handler(args)
        except httpx.HTTPStatusError as exc:
            parser.exit(1, f"HTTP {exc.response.status_code}: {exc.response.text}\n")
        except Exception as exc:
            parser.exit(1, f"error: {exc}\n")
