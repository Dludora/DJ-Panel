from __future__ import annotations

import argparse

import httpx

import dj_panel.cli.commands as commands


class CliExecutor:
    def __init__(self) -> None:
        self._groups = commands.build_command_groups()

    def execute(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
        group_name = getattr(args, "handler_group", None)
        method_name = getattr(args, "handler_method", None)
        if group_name is None or method_name is None:
            parser.error("no command configured")

        group = self._groups.get(group_name)
        if group is None:
            parser.error(f"unknown command group: {group_name}")

        handler = getattr(group, method_name, None)
        if handler is None:
            parser.error(f"unknown command handler: {group_name}.{method_name}")

        try:
            handler(args)
        except httpx.HTTPStatusError as exc:
            parser.exit(1, f"HTTP {exc.response.status_code}: {exc.response.text}\n")
        except Exception as exc:
            parser.exit(1, f"error: {exc}\n")
