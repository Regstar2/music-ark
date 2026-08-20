"""Structured process bridge for production Yandex upload and managed-playlist workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError
from musicark.recovery.managed_playlists import ManagedPlaylistError, ManagedPlaylistService
from musicark.upload.batch_service import YandexBatchUploadError, YandexBatchUploadService
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
    """Raised before any mutation when a structured request is invalid."""


def _read_object() -> dict[str, Any]:
    raw = os.getenv(UPLOAD_PAYLOAD_ENV, "")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UploadBridgeRequestError("Upload payload must be valid JSON.") from exc
    if not isinstance(decoded, dict):
        raise UploadBridgeRequestError("Upload payload must be a JSON object.")
    return dict(decoded)


def _exact(decoded: dict[str, Any], keys: set[str], label: str) -> None:
    if set(decoded) != keys:
        raise UploadBridgeRequestError(f"{label} payload contains unexpected or missing fields.")


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise UploadBridgeRequestError(f"{name} must be a positive integer.")
    return int(value)


def _string(value: Any, name: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise UploadBridgeRequestError(f"{name} must be a non-empty bounded string.")
    return value.strip()


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise UploadBridgeRequestError(f"{name} must be a boolean.")
    return value


def _read_upload_payload() -> dict[str, Any]:
    decoded = _read_object()
    _exact(decoded, _REQUIRED_UPLOAD_KEYS, "Single-track upload")
    return {
        "local_file_id": _positive_int(decoded.get("local_file_id"), "local_file_id"),
        "playlist_kind": _string(decoded.get("playlist_kind"), "playlist_kind"),
        "confirm": _boolean(decoded.get("confirm"), "confirm"),
        "rights_confirmed": _boolean(decoded.get("rights_confirmed"), "rights_confirmed"),
    }


def _read_batch_payload() -> dict[str, Any]:
    decoded = _read_object()
    keys = {
        "local_file_ids",
        "playlist_kind",
        "confirm",
        "rights_confirmed",
        "batch_id",
        "allow_stale_reupload",
    }
    _exact(decoded, keys, "Batch upload")
    raw_ids = decoded.get("local_file_ids")
    if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > YandexBatchUploadService.MAX_BATCH_SIZE:
        raise UploadBridgeRequestError("local_file_ids must be a non-empty bounded array.")
    ids = [_positive_int(value, "local_file_id") for value in raw_ids]
    if len(set(ids)) != len(ids):
        raise UploadBridgeRequestError("local_file_ids must not contain duplicates.")
    batch_id = decoded.get("batch_id")
    if batch_id is not None:
        batch_id = _string(batch_id, "batch_id", max_length=128)
    return {
        "local_file_ids": ids,
        "playlist_kind": _string(decoded.get("playlist_kind"), "playlist_kind"),
        "confirm": _boolean(decoded.get("confirm"), "confirm"),
        "rights_confirmed": _boolean(decoded.get("rights_confirmed"), "rights_confirmed"),
        "batch_id": batch_id,
        "allow_stale_reupload": _boolean(
            decoded.get("allow_stale_reupload"), "allow_stale_reupload"
        ),
    }


def _read_batch_id_payload() -> str:
    decoded = _read_object()
    _exact(decoded, {"batch_id"}, "Batch state")
    return _string(decoded.get("batch_id"), "batch_id", max_length=128)


def _read_managed_set_payload() -> tuple[str, str]:
    decoded = _read_object()
    _exact(decoded, {"role", "playlist_kind"}, "Managed playlist")
    return (
        _string(decoded.get("role"), "role", max_length=32),
        _string(decoded.get("playlist_kind"), "playlist_kind"),
    )


def _read_managed_clear_payload() -> str:
    decoded = _read_object()
    _exact(decoded, {"role"}, "Managed playlist clear")
    return _string(decoded.get("role"), "role", max_length=32)


def _read_managed_ensure_payload() -> bool:
    decoded = _read_object()
    _exact(decoded, {"confirm_create"}, "Managed playlist ensure")
    return _boolean(decoded.get("confirm_create"), "confirm_create")


def _database_path(base_dir: Path | None) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    if raw.is_absolute():
        return raw
    root = base_dir if base_dir is not None else Path.home()
    return root / raw


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
    parser.add_argument(
        "command",
        choices=(
            "yandex_upload_targets",
            "yandex_upload_track",
            "yandex_upload_batch",
            "yandex_upload_batch_status",
            "yandex_upload_batch_cancel",
            "yandex_managed_playlists_get",
            "yandex_managed_playlists_ensure",
            "yandex_managed_playlist_set",
            "yandex_managed_playlist_clear",
        ),
    )
    return parser


def _dispatch(command: str, base_dir: Path | None) -> dict[str, Any]:
    if command == "yandex_upload_targets":
        return _targets(base_dir)
    if command == "yandex_upload_track":
        request = _read_upload_payload()
        return YandexSingleTrackUploadService(base_dir=base_dir).upload_track(**request).to_dict()
    if command == "yandex_upload_batch":
        return YandexBatchUploadService(base_dir=base_dir).execute(**_read_batch_payload())
    if command == "yandex_upload_batch_status":
        return YandexBatchUploadService(base_dir=base_dir).status(_read_batch_id_payload())
    if command == "yandex_upload_batch_cancel":
        return YandexBatchUploadService(base_dir=base_dir).cancel(_read_batch_id_payload())

    managed = ManagedPlaylistService(_database_path(base_dir), base_dir=base_dir)
    if command == "yandex_managed_playlists_get":
        return managed.state()
    if command == "yandex_managed_playlists_ensure":
        return managed.ensure(confirm_create=_read_managed_ensure_payload())
    if command == "yandex_managed_playlist_set":
        role, playlist_kind = _read_managed_set_payload()
        return managed.set_role(role=role, playlist_kind=playlist_kind)
    if command == "yandex_managed_playlist_clear":
        return managed.clear_role(_read_managed_clear_payload())
    raise UploadBridgeRequestError("Unsupported upload command.")


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        payload = _dispatch(args.command, base_dir)
    except (UploadBridgeRequestError, YandexBatchUploadError, ManagedPlaylistError) as exc:
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
