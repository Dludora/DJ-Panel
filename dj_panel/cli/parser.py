from __future__ import annotations

import argparse

from dj_panel.cli.commands import COMMAND_GROUP_TYPES, register_command_groups
from dj_panel.cli.executor import CliExecutor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dj-panel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_command_groups(subparsers, COMMAND_GROUP_TYPES)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    CliExecutor().execute(parser, args)
