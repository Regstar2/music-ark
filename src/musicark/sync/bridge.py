"""JSON subprocess bridge for MusicArk Controlled Sync."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from musicark.core.errors import MusicArkError
from musicark.download.service import DownloadServiceError

from .service import SyncService, SyncServiceError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-sync-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument(
        "command",
        choices=(
            "scopes",
            "target",
            "set_target",
            "create",
            "current",
            "plan",
            "history",
            "apply",
            "cancel",
            "set_action",
            "recovery_summary",
            "recovery_tracks",
            "managed_playlists",
        ),
    )
    parser.add_argument("--plan-id", default=None)
    parser.add_argument("--scope-type", default="all")
    parser.add_argument("--scope-id", default=None)
    parser.add_argument("--target-path", default=None)
    parser.add_argument("--external-id", default=None)
    parser.add_argument("--action", default=None)
    parser.add_argument("--filter", default="all")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--rights-confirmed", action="store_true")
    return parser


def _required(value: str | None, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise SyncServiceError(f"{name} is required.", code="invalid_request")
    return clean


def _dispatch(args: argparse.Namespace, service: SyncService) -> dict[str, Any]:
    if args.command == "scopes":
        return service.scopes()
    if args.command == "target":
        return service.target()
    if args.command == "set_target":
        return service.set_target(_required(args.target_path, "--target-path"))
    if args.command == "create":
        return service.create_plan(scope_type=args.scope_type, scope_id=args.scope_id)
    if args.command == "current":
        return service.current()
    if args.command == "plan":
        return service.plan(_required(args.plan_id, "--plan-id"))
    if args.command == "history":
        return service.history(limit=args.limit)
    if args.command == "apply":
        return service.apply(
            _required(args.plan_id, "--plan-id"),
            confirm=args.confirm,
            rights_confirmed=args.rights_confirmed,
        )
    if args.command == "cancel":
        return service.cancel(_required(args.plan_id, "--plan-id"))
    if args.command == "set_action":
        return service.set_action(
            external_id=_required(args.external_id, "--external-id"),
            action=_required(args.action, "--action"),
        )
    if args.command == "recovery_summary":
        return service.recovery(filter_name="all", limit=1, offset=0).get("summary", {})
    if args.command == "recovery_tracks":
        return service.recovery(
            filter_name=args.filter,
            limit=max(1, min(args.limit, 1000)),
            offset=max(0, args.offset),
        )
    if args.command == "managed_playlists":
        return service.managed_playlists()
    raise SyncServiceError("Unsupported command.", code="invalid_request")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        service = SyncService(base_dir=Path(args.base_dir) if args.base_dir else None)
        payload = _dispatch(args, service)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except SyncServiceError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False))
        return 2
    except DownloadServiceError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}, ensure_ascii=False))
        return 2
    except (MusicArkError, ValueError, OSError):
        print(
            json.dumps(
                {"error": {"code": "sync_error", "message": "Controlled Sync could not complete safely."}},
                ensure_ascii=False,
            )
        )
        return 2
    except Exception:  # pragma: no cover - bridge crash guard
        print(
            json.dumps(
                {"error": {"code": "unexpected_error", "message": "Controlled Sync failed unexpectedly."}},
                ensure_ascii=False,
            )
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
