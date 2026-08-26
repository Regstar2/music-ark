"""Streaming process bridge for long identity-matching runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from musicark.mvp_bridge import _error_payload

from .responsive_service import ResponsiveMatchingService

PROGRESS_PREFIX = "__MUSICARK_MATCHING_PROGRESS__"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-matching-progress-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=("matching_run",))
    parser.add_argument("--provider-id", default="yandex_music")
    return parser


def _emit_progress(processed: int, total: int) -> None:
    payload: dict[str, Any] = {
        "processed": max(0, int(processed)),
        "total": max(0, int(total)),
    }
    print(
        f"{PROGRESS_PREFIX}{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}",
        file=sys.stderr,
        flush=True,
    )


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        payload = ResponsiveMatchingService(
            base_dir=base_dir,
            provider_id=args.provider_id,
        ).run(progress=_emit_progress)
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes errors.
        print(json.dumps(_error_payload(exc), ensure_ascii=False), flush=True)
        return 2
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
