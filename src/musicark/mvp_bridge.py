"""JSON process bridge for MusicArk desktop UI (Yandex + Local + Matching)."""

from __future__ import annotations

import argparse
from enum import Enum
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.core.errors import MusicArkError, StorageError
from musicark.credentials import CredentialStoreError
from musicark.local_library.service import LocalLibraryService
from musicark.matching.service import MatchingService
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)
from musicark.yandex_library import YandexLibraryService


class BridgeRequestError(MusicArkError):
    pass


class BridgeErrorCode(str, Enum):
    TOKEN_MISSING = "token_missing"
    AUTHENTICATION_FAILED = "authentication_failed"
    YANDEX_REQUEST_FAILED = "yandex_request_failed"
    CREDENTIAL_STORE_FAILED = "credential_store_failed"
    CACHE_FAILED = "cache_failed"
    INVALID_REQUEST = "invalid_request"
    UNEXPECTED_ERROR = "unexpected_error"


def bootstrap(service: Any) -> dict[str, Any]:
    return service.bootstrap()


def login(token: str, service: Any) -> dict[str, Any]:
    return service.login(token)


def refresh(service: Any) -> dict[str, Any]:
    return service.refresh()


def liked_refresh(service: Any) -> dict[str, Any]:
    return service.liked_refresh()


def playlists(service: Any) -> dict[str, Any]:
    return service.playlists()


def playlist(external_id: str, service: Any) -> dict[str, Any]:
    return service.playlist(external_id)


def playlist_refresh(external_id: str, service: Any) -> dict[str, Any]:
    return service.playlist_refresh(external_id)


def library_refresh(service: Any) -> dict[str, Any]:
    return service.library_refresh()


def cached(service: Any) -> dict[str, Any]:
    return service.cached()


def logout(service: Any) -> dict[str, Any]:
    return service.logout()


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, YandexTokenMissingError):
        code = BridgeErrorCode.TOKEN_MISSING
    elif isinstance(exc, YandexAuthenticationError):
        code = BridgeErrorCode.AUTHENTICATION_FAILED
    elif isinstance(exc, YandexMusicError):
        code = BridgeErrorCode.YANDEX_REQUEST_FAILED
    elif isinstance(exc, CredentialStoreError):
        code = BridgeErrorCode.CREDENTIAL_STORE_FAILED
    elif isinstance(exc, StorageError):
        code = BridgeErrorCode.CACHE_FAILED
    elif isinstance(exc, (BridgeRequestError, ValueError)):
        code = BridgeErrorCode.INVALID_REQUEST
    else:
        code = BridgeErrorCode.UNEXPECTED_ERROR
    return {"error": {"code": code.value, "message": str(exc)}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-mvp-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument(
        "command",
        choices=(
            "bootstrap", "login", "refresh", "liked_refresh", "playlists", "playlist",
            "playlist_refresh", "library_refresh", "cached", "logout",
            "local_roots", "local_root_add", "local_root_remove", "local_scan",
            "local_tracks", "local_track", "local_stats",
            "matching_summary", "matching_run", "matching_results", "matching_result",
            "matching_accept", "matching_reject",
        ),
    )
    parser.add_argument("--playlist-id", default=None)
    parser.add_argument("--root-id", type=int, default=None)
    parser.add_argument("--track-id", type=int, default=None)
    parser.add_argument("--provider-id", default="yandex_music")
    parser.add_argument("--external-id", default=None)
    parser.add_argument("--local-file-id", type=int, default=None)
    parser.add_argument("--status", default="")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--search", default="")
    parser.add_argument("--sort", default="artist")
    return parser


def _required_text(value: str | None, flag: str) -> str:
    clean = (value or "").strip()
    if not clean:
        raise BridgeRequestError(f"{flag} is required for this command.")
    return clean


def _required_playlist_id(value: str | None) -> str:
    return _required_text(value, "--playlist-id")


def _required_root_id(value: int | None) -> int:
    if value is None:
        raise BridgeRequestError("--root-id is required for this command.")
    return int(value)


def _required_track_id(value: int | None) -> int:
    if value is None:
        raise BridgeRequestError("--track-id is required for this command.")
    return int(value)


def _required_local_file_id(value: int | None) -> int:
    if value is None:
        raise BridgeRequestError("--local-file-id is required for this command.")
    return int(value)


def _local_payload(args: argparse.Namespace, base_dir: Path | None) -> dict[str, Any]:
    service = LocalLibraryService(base_dir=base_dir)
    if args.command == "local_roots":
        return service.roots()
    if args.command == "local_root_add":
        path = os.getenv("MUSICARK_LOCAL_ROOT", "").strip()
        if not path:
            raise BridgeRequestError("Local root path is missing from bridge environment.")
        return service.add_root(path)
    if args.command == "local_root_remove":
        return service.remove_root(_required_root_id(args.root_id))
    if args.command == "local_scan":
        return service.scan(args.root_id)
    if args.command == "local_tracks":
        return service.tracks(
            limit=args.limit,
            offset=args.offset,
            search=args.search,
            sort=args.sort,
            root_id=args.root_id,
        )
    if args.command == "local_track":
        return service.track(_required_track_id(args.track_id))
    if args.command == "local_stats":
        return service.stats()
    raise BridgeRequestError(f"Unknown local command: {args.command}")


def _matching_payload(args: argparse.Namespace, base_dir: Path | None) -> dict[str, Any]:
    service = MatchingService(base_dir=base_dir, provider_id=args.provider_id)
    if args.command == "matching_summary":
        return service.summary()
    if args.command == "matching_run":
        return service.run()
    if args.command == "matching_results":
        return service.results(
            limit=args.limit,
            offset=args.offset,
            status=args.status,
            search=args.search,
            sort=args.sort,
        )
    external_id = _required_text(args.external_id, "--external-id")
    if args.command == "matching_result":
        return service.result(external_id)
    local_file_id = _required_local_file_id(args.local_file_id)
    if args.command == "matching_accept":
        return service.accept(external_id, local_file_id)
    if args.command == "matching_reject":
        return service.reject(external_id, local_file_id)
    raise BridgeRequestError(f"Unknown matching command: {args.command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        if args.command.startswith("local_"):
            payload = _local_payload(args, base_dir)
        elif args.command.startswith("matching_"):
            payload = _matching_payload(args, base_dir)
        else:
            service = YandexLibraryService(base_dir=base_dir)
            if args.command == "bootstrap":
                payload = bootstrap(service)
            elif args.command == "login":
                payload = login(os.getenv("YANDEX_MUSIC_TOKEN", "").strip(), service)
            elif args.command == "refresh":
                payload = refresh(service)
            elif args.command == "liked_refresh":
                payload = liked_refresh(service)
            elif args.command == "playlists":
                payload = playlists(service)
            elif args.command == "playlist":
                payload = playlist(_required_playlist_id(args.playlist_id), service)
            elif args.command == "playlist_refresh":
                payload = playlist_refresh(_required_playlist_id(args.playlist_id), service)
            elif args.command == "library_refresh":
                payload = library_refresh(service)
            elif args.command == "cached":
                payload = cached(service)
            else:
                payload = logout(service)
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes errors.
        print(json.dumps(_error_payload(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
