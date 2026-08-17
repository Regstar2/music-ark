"""JSON process bridge for explicit recording-variant acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .acceptance import VariantAcceptanceError, VariantAcceptanceService


_COMMANDS = ("get", "accept", "reset")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-variant-acceptance-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--provider-id", default="yandex_music")
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--local-file-id", type=int, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    service = VariantAcceptanceService(
        base_dir=Path(args.base_dir) if args.base_dir else None,
        provider_id=args.provider_id,
    )
    try:
        if args.command == "accept":
            payload = service.accept(args.external_id, args.local_file_id)
        elif args.command == "reset":
            payload = service.reset(args.external_id, args.local_file_id)
        else:
            payload = service.get(args.external_id, args.local_file_id)
    except (VariantAcceptanceError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_request", "message": str(exc)}}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001 - subprocess boundary.
        print(json.dumps({"error": {"code": "unexpected_error", "message": str(exc)}}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
