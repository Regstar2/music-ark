"""Structured process bridge for production manual Yandex uploads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.core.errors import MusicArkError
from musicark.upload.yandex_service import YandexSingleTrackUploadService
from musicark.yandex_library import YandexLibraryService


UPLOAD_PAYLOAD_ENV = "MUSICARK_YANDEX_UPLOAD_PAYLOAD"
_REQUIRED_UPLOAD_KEYS = {
    "local_file_id",
    "playlist_kind",
    "confirm",
    "rights_confirmed",
}


class UploadBridgeRequestError(MusicArkError):
    """Raised before any mutation when the structured upload request is invalid."""


def _read_upload_payload() -> dict[str, Any]:
    raw = os.getenv(UPLOAD_PAYLOAD_ENV, "")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UploadBridgeRequestError("Upload payload must be valid JSON.") from exc
    if not isinstance(decoded, dict) or set(decoded) != _REQUIRED_UPLOAD_KEYS:
        raise UploadBridgeRequestError("Upload payload must contain exactly the four required fields.")
    local_file_id = decoded.get("local_file_id")
    playlist_kind = decoded.get("playlist_kind")
    confirm = decoded.get("confirm")
    rights_confirmed = decoded.get("rights_confirmed")
    if isinstance(local_file_id, bool) or not isinstance(local_file_id, int) or local_file_id <= 0:
        raise UploadBridgeRequestError("local_file_id must be a positive integer.")
    if not isinstance(playlist_kind, str) or not playlist_kind.strip():
        raise UploadBridgeRequestError("playlist_kind must be a non-empty string.")
    if not isinstance(confirm, bool) or not isinstance(rights_confirmed, bool):
        raise UploadBridgeRequestError("confirm and rights_confirmed must be booleans.")
    return {
        "local_file_id": local_file_id,
        "playlist_kind": playlist_kind.strip(),
        "confirm": confirm,
        "rights_confirmed": rights_confirmed,
    }


def _targets(base_dir: Path | None) -> dict[str, Any]:
    """Expose only cached personal playlist metadata from the existing library cache."""
    state = YandexLibraryService(base_dir=base_dir).playlists()
    session = state.get("session") if isinstance(state, dict) else {}
    index = state.get("playlists") if isinstance(state, dict) else {}
    items = index.get("items") if isinstance(index, dict) else []
    safe_items: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("externalId") or "").strip()
            if not kind:
                continue
            safe_items.append(
                {
                    "playlistKind": kind,
                    "title": str(item.get("title") or kind),
                    "trackCount": int(item.get("trackCount") or 0),
                }
            )
    return {
        "authenticated": bool(
            isinstance(session, dict) and session.get("hasStoredToken") is True
        ),
        "playlists": safe_items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-yandex-upload-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=("yandex_upload_targets", "yandex_upload_track"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        if args.command == "yandex_upload_targets":
            payload = _targets(base_dir)
        else:
            request = _read_upload_payload()
            result = YandexSingleTrackUploadService(base_dir=base_dir).upload_track(**request)
            payload = result.to_dict()
    except UploadBridgeRequestError as exc:
        print(json.dumps({"error": {"code": "invalid_request", "message": str(exc)}}, ensure_ascii=False))
        return 2
    except Exception:  # noqa: BLE001 - do not expose raw provider/transport exception text.
        print(
            json.dumps(
                {
                    "error": {
                        "code": "upload_bridge_failed",
                        "message": "The Yandex upload bridge could not complete the request safely.",
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
