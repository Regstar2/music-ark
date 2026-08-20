"""Bounded JSON bridge for MusicArk v0.11.1 recovery summaries and rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from musicark.core.config import load_config
from musicark.recovery.service import RecoveryService


def _database_path(base_dir: Path | None) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    if raw.is_absolute():
        return raw
    root = base_dir if base_dir is not None else Path.home()
    return root / raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-recovery-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=("recovery_summary", "recovery_tracks"))
    parser.add_argument("--filter", default="all", choices=("all", "recoverable", "missing_local", "needs_review"))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--offset", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = RecoveryService(_database_path(base_dir))
        payload = service.summary() if args.command == "recovery_summary" else service.payload(
            filter_name=args.filter,
            limit=max(1, min(args.limit, 1000)),
            offset=max(0, args.offset),
        )
    except Exception:  # noqa: BLE001 - no raw provider/storage exception crosses the process boundary
        print(
            json.dumps(
                {
                    "error": {
                        "code": "recovery_bridge_failed",
                        "message": "Recovery state could not be loaded safely.",
                    }
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
