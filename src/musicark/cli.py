"""Minimal CLI entrypoint for MusicArk v0.1."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from musicark.core.app import MusicArkApp
from musicark.core.config import load_config
from musicark.core.logging_setup import setup_logging


def build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="musicark")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Override base directory used for config and local DB.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health-check", help="Show basic core health state.")
    subparsers.add_parser("db-init", help="Initialize SQLite schema.")
    subparsers.add_parser("config-show", help="Print current configuration.")
    return parser


def main() -> int:
    """Run MusicArk CLI command."""
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None

    app = MusicArkApp(base_dir=base_dir)
    setup_logging(level=app.config.log_level)

    if args.command == "health-check":
        print(json.dumps(app.health_check(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "db-init":
        db_path = app.db_init()
        print(f"SQLite initialized: {db_path}")
        return 0

    if args.command == "config-show":
        config = load_config(base_dir)
        print(json.dumps(asdict(config), ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
