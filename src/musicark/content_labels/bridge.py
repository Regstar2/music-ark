"""JSON process bridge for user-assigned track content-version labels."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .service import ContentLabelError, ContentLabelService


_COMMANDS = ("batch", "set_local", "set_provider")


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContentLabelError(f"{name} contains invalid JSON.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-content-label-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--local-file-id", type=int, default=None)
    parser.add_argument("--provider-id", default="yandex_music")
    parser.add_argument("--external-id", default="")
    parser.add_argument("--label", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    service = ContentLabelService(base_dir=base_dir)
    try:
        if args.command == "batch":
            body = _json_env("MUSICARK_CONTENT_LABEL_PAYLOAD", {})
            if not isinstance(body, dict):
                raise ContentLabelError("Batch payload must be a JSON object.")
            local_ids = body.get("localFileIds") or []
            external_ids = body.get("externalIds") or []
            if not isinstance(local_ids, list) or not isinstance(external_ids, list):
                raise ContentLabelError("Batch ids must be JSON arrays.")
            payload = service.batch(
                local_file_ids=[int(item) for item in local_ids],
                provider_id=args.provider_id,
                external_ids=[str(item) for item in external_ids],
            )
        elif args.command == "set_local":
            if args.local_file_id is None:
                raise ContentLabelError("--local-file-id is required.")
            payload = service.set_local(int(args.local_file_id), args.label)
        else:
            payload = service.set_provider(
                args.external_id,
                args.label,
                provider_id=args.provider_id,
            )
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes errors.
        code = "invalid_request" if isinstance(exc, (ContentLabelError, ValueError)) else "unexpected_error"
        print(json.dumps({"error": {"code": code, "message": str(exc)}}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
