"""Minimal JSON bridge for the MusicArk Yandex likes MVP.

The desktop UI passes the Yandex token through the child-process environment.
The token is never accepted as a command-line argument and is never persisted
by this module.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any

from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexMusicProvider,
    YandexTokenMissingError,
)


class BridgeErrorCode(str, Enum):
    TOKEN_MISSING = "token_missing"
    AUTHENTICATION_FAILED = "authentication_failed"
    YANDEX_REQUEST_FAILED = "yandex_request_failed"
    UNEXPECTED_ERROR = "unexpected_error"


def login(
    base_dir: Path | None = None,
    provider: YandexMusicProvider | None = None,
) -> dict[str, Any]:
    """Validate the current Yandex token and return account identity."""
    active_provider = provider or YandexMusicProvider(base_dir=base_dir)
    return active_provider.auth_check()


def liked_tracks(
    base_dir: Path | None = None,
    provider: YandexMusicProvider | None = None,
) -> dict[str, Any]:
    """Return the current user's liked tracks without writing them to SQLite."""
    active_provider = provider or YandexMusicProvider(base_dir=base_dir)
    tracks = [asdict(track) for track in active_provider.list_tracks()]
    return {"count": len(tracks), "tracks": tracks}


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, YandexTokenMissingError):
        code = BridgeErrorCode.TOKEN_MISSING
    elif isinstance(exc, YandexAuthenticationError):
        code = BridgeErrorCode.AUTHENTICATION_FAILED
    elif isinstance(exc, YandexMusicError):
        code = BridgeErrorCode.YANDEX_REQUEST_FAILED
    else:
        code = BridgeErrorCode.UNEXPECTED_ERROR

    return {
        "error": {
            "code": code.value,
            "message": str(exc),
        }
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-mvp-bridge")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Repository root used by provider-local configuration fallback.",
    )
    parser.add_argument("command", choices=("login", "likes"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None

    try:
        if args.command == "login":
            payload = login(base_dir=base_dir)
        else:
            payload = liked_tracks(base_dir=base_dir)
    except Exception as exc:  # noqa: BLE001 - bridge converts errors at process boundary.
        print(json.dumps(_error_payload(exc), ensure_ascii=False))
        return 2

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
