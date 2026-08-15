"""JSON process bridge dedicated to the v0.7 download workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.credentials import CredentialStoreError
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)

from .service import DownloadService, DownloadServiceError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-download-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument(
        "command",
        choices=(
            "summary",
            "tasks",
            "enqueue",
            "enqueue_wanted",
            "run",
            "retry",
            "cancel",
            "clear_completed",
            "settings",
            "set_target",
            "recover",
        ),
    )
    parser.add_argument("--external-id", default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--status", default="")
    parser.add_argument("--limit", type=int, default=1000)
    return parser


def _required(value: str | None, name: str) -> str:
    clean = (value or "").strip()
    if not clean:
        raise DownloadServiceError(f"{name} is required.", code="invalid_request")
    return clean


def _dispatch(args: argparse.Namespace, service: DownloadService) -> dict[str, Any]:
    if args.command == "summary":
        return service.summary()
    if args.command == "tasks":
        return service.tasks(status=args.status, limit=args.limit)
    if args.command == "enqueue":
        return service.enqueue(_required(args.external_id, "--external-id"))
    if args.command == "enqueue_wanted":
        return service.enqueue_wanted()
    if args.command == "run":
        return service.run()
    if args.command == "retry":
        return service.retry(_required(args.task_id, "--task-id"))
    if args.command == "cancel":
        return service.cancel(_required(args.task_id, "--task-id"))
    if args.command == "clear_completed":
        return service.clear_completed()
    if args.command == "settings":
        return service.settings()
    if args.command == "set_target":
        path = os.getenv("MUSICARK_DOWNLOAD_TARGET", "").strip()
        if not path:
            raise DownloadServiceError("Download target path is missing.", code="invalid_request")
        return service.set_target(path)
    if args.command == "recover":
        return service.recover_interrupted()
    raise DownloadServiceError("Unsupported download command.", code="invalid_request")


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, DownloadServiceError):
        code = exc.code
    elif isinstance(exc, (YandexTokenMissingError, YandexAuthenticationError, CredentialStoreError)):
        code = "authentication"
    elif isinstance(exc, YandexMusicError):
        code = "provider_request"
    else:
        code = "unexpected_error"
    return {"error": {"code": code, "message": str(exc)}}


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = DownloadService(base_dir=base_dir)
        payload = _dispatch(args, service)
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes failures.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
