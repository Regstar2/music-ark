"""JSON process bridge for the explicit Local Metadata Editor."""

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

from .service import MetadataEditorError, MetadataEditorService


_COMMANDS = (
    "local_metadata_get",
    "local_metadata_update",
    "local_artwork_batch",
    "yandex_metadata_search",
    "yandex_metadata_get",
    "local_metadata_compare_yandex",
    "local_metadata_apply_yandex",
)


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataEditorError(f"{name} contains invalid JSON.") from exc


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, YandexTokenMissingError):
        code = "token_missing"
    elif isinstance(exc, YandexAuthenticationError):
        code = "authentication_failed"
    elif isinstance(exc, YandexMusicError):
        code = "yandex_request_failed"
    elif isinstance(exc, CredentialStoreError):
        code = "credential_store_failed"
    elif isinstance(exc, (MetadataEditorError, ValueError)):
        code = "invalid_request"
    else:
        code = "unexpected_error"
    return {"error": {"code": code, "message": str(exc)}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-metadata-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--local-file-id", type=int, default=None)
    parser.add_argument("--external-id", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--artist", default="")
    parser.add_argument("--bind-identity", action="store_true")
    return parser


def _file_id(value: int | None) -> int:
    if value is None:
        raise MetadataEditorError("--local-file-id is required for this command.")
    return int(value)


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    service = MetadataEditorService(base_dir=base_dir)
    try:
        if args.command == "local_metadata_get":
            payload = service.get(_file_id(args.local_file_id))
        elif args.command == "local_metadata_update":
            body = _json_env("MUSICARK_METADATA_PAYLOAD", {})
            if not isinstance(body, dict):
                raise MetadataEditorError("Metadata payload must be a JSON object.")
            changes = body.get("changes") or {}
            if not isinstance(changes, dict):
                raise MetadataEditorError("Metadata changes must be a JSON object.")
            payload = service.update(
                _file_id(args.local_file_id), dict(changes),
                confirm=body.get("confirm") is True,
            )
        elif args.command == "local_artwork_batch":
            values = _json_env("MUSICARK_LOCAL_FILE_IDS", [])
            if not isinstance(values, list):
                raise MetadataEditorError("Artwork batch ids must be a JSON array.")
            payload = service.artwork_batch([int(item) for item in values])
        elif args.command == "yandex_metadata_search":
            payload = service.yandex_search(
                _file_id(args.local_file_id), title=args.title, artist=args.artist, query=args.query
            )
        elif args.command == "yandex_metadata_get":
            payload = service.yandex_get(args.external_id)
        elif args.command == "local_metadata_compare_yandex":
            payload = service.compare_yandex(_file_id(args.local_file_id), args.external_id)
        else:
            body = _json_env("MUSICARK_METADATA_PAYLOAD", {})
            selected = body.get("selectedFields") if isinstance(body, dict) else None
            if selected is None:
                selected = []
            if not isinstance(selected, list):
                raise MetadataEditorError("selectedFields must be a JSON array.")
            payload = service.apply_yandex(
                _file_id(args.local_file_id), args.external_id,
                [str(item) for item in selected],
                bind_identity=bool(args.bind_identity),
                confirm=bool(isinstance(body, dict) and body.get("confirm") is True),
            )
    except Exception as exc:  # noqa: BLE001 - bridge is the public process boundary.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
