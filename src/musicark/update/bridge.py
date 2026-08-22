"""JSON process bridge for update discovery and explicit installer actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .models import UpdateError
from .service import UpdateService

_PAYLOAD_ENV = "MUSICARK_UPDATE_PAYLOAD"


def _payload() -> dict[str, Any]:
    raw = os.getenv(_PAYLOAD_ENV, "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Update bridge payload is invalid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Update bridge payload must be a JSON object.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-update-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=("check", "prepare", "apply"))
    return parser


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, UpdateError):
        return {"error": {"code": exc.code.value, "message": str(exc)}}
    if isinstance(exc, ValueError):
        return {"error": {"code": "invalid_request", "message": str(exc)}}
    return {"error": {"code": "update_failed", "message": exc.__class__.__name__}}


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = UpdateService(base_dir=base_dir)
        if args.command == "check":
            result = service.check()
        elif args.command == "prepare":
            result = service.prepare()
        else:
            payload = _payload()
            result = service.launch_prepared(
                str(payload.get("version", "")).strip(),
                confirm=payload.get("confirm") is True,
            )
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes failures.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
