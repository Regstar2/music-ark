"""JSON process bridge for the MusicArk persistent-library desktop MVP.

The sign-in token is accepted only through the child-process environment. After
successful sign-in it is stored by ``SystemCredentialStore`` and later bridge
commands use the OS credential store; no token is placed in argv or SQLite.
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.core.errors import StorageError
from musicark.credentials import CredentialStoreError
from musicark.persistent_library import PersistentLibraryService
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)


class BridgeErrorCode(str, Enum):
    TOKEN_MISSING = "token_missing"
    AUTHENTICATION_FAILED = "authentication_failed"
    YANDEX_REQUEST_FAILED = "yandex_request_failed"
    CREDENTIAL_STORE_FAILED = "credential_store_failed"
    CACHE_FAILED = "cache_failed"
    UNEXPECTED_ERROR = "unexpected_error"


def bootstrap(service: PersistentLibraryService) -> dict[str, Any]:
    return service.bootstrap()


def login(token: str, service: PersistentLibraryService) -> dict[str, Any]:
    return service.login(token)


def refresh(service: PersistentLibraryService) -> dict[str, Any]:
    return service.refresh()


def cached(service: PersistentLibraryService) -> dict[str, Any]:
    return service.cached()


def logout(service: PersistentLibraryService) -> dict[str, Any]:
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
    else:
        code = BridgeErrorCode.UNEXPECTED_ERROR

    return {"error": {"code": code.value, "message": str(exc)}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-mvp-bridge")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Repository root used for MusicArk local data/config resolution.",
    )
    parser.add_argument(
        "command",
        choices=("bootstrap", "login", "refresh", "cached", "logout"),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None

    try:
        service = PersistentLibraryService(base_dir=base_dir)
        if args.command == "bootstrap":
            payload = bootstrap(service)
        elif args.command == "login":
            token = os.getenv("YANDEX_MUSIC_TOKEN", "").strip()
            payload = login(token, service)
        elif args.command == "refresh":
            payload = refresh(service)
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
