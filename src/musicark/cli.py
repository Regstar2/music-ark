"""Minimal CLI entrypoint for MusicArk v0.1."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from musicark.core.app import MusicArkApp
from musicark.core.config import load_config
from musicark.core.logging_setup import setup_logging
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexMusicProvider,
    YandexTokenMissingError,
)


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

    yandex_parser = subparsers.add_parser("yandex", help="Run Yandex provider commands.")
    yandex_subparsers = yandex_parser.add_subparsers(dest="yandex_command", required=True)
    yandex_subparsers.add_parser("auth-check", help="Validate Yandex token and account access.")
    yandex_subparsers.add_parser("scan-likes", help="Scan liked tracks only.")
    yandex_subparsers.add_parser("scan-playlists", help="Scan playlists only.")
    yandex_subparsers.add_parser("scan-all", help="Scan account, likes and playlists.")
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

    if args.command == "yandex":
        provider = YandexMusicProvider(base_dir=base_dir)
        try:
            if args.yandex_command == "auth-check":
                print(json.dumps(provider.auth_check(), ensure_ascii=False, indent=2))
                return 0
            if args.yandex_command == "scan-likes":
                print(
                    json.dumps(
                        [asdict(track) for track in provider.list_tracks()],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if args.yandex_command == "scan-playlists":
                print(
                    json.dumps(
                        [asdict(playlist) for playlist in provider.list_playlists()],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if args.yandex_command == "scan-all":
                db_path = app.db_init()
                result = provider.scan_all(database_path=db_path)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
        except (YandexTokenMissingError, YandexAuthenticationError, YandexMusicError) as exc:
            print(str(exc))
            return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
