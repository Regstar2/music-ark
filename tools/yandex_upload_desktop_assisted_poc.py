"""Verify one official-desktop-assisted Yandex upload by MusicArk read-back.

This PoC deliberately does not extract the desktop application's credentials and
does not perform the upload HTTP request itself. MusicArk snapshots an explicit
user-owned playlist, the user performs exactly one normal visible upload in the
already-authenticated official Yandex Music desktop client, and MusicArk then
polls the same playlist for one unambiguous new track identity.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable

import yandex_upload_live_poc as live


_TRUE = {"1", "true", "yes", "on"}


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUE


def verify_readback(
    *,
    before_ids: set[str],
    read_current_ids: Callable[[], set[str]],
    attempts: int,
    delay: float,
) -> dict[str, Any]:
    """Poll until one unambiguous new ID appears or the bounded window ends."""
    result = live._classify_readback_identity(before_ids, before_ids, None)  # noqa: SLF001
    attempts_used = 0
    for attempt in range(1, attempts + 1):
        attempts_used = attempt
        current_ids = set(read_current_ids())
        result = live._classify_readback_identity(before_ids, current_ids, None)  # noqa: SLF001
        if result["verified"] or result["ambiguous"]:
            break
        if attempt < attempts:
            time.sleep(delay)
    return {**result, "attemptsUsed": attempts_used}


def run(args: argparse.Namespace, *, prompt: Callable[[str], str] = input) -> tuple[dict[str, Any], int]:
    base_dir = Path(args.base_dir) if args.base_dir else None
    live._require_research_opt_in(base_dir)  # noqa: SLF001
    if not args.confirm_owned_file:
        raise live.YandexUploadProtocolError("Desktop-assisted PoC requires --confirm-owned-file.")
    if not args.confirm_desktop_upload:
        raise live.YandexUploadProtocolError("Desktop-assisted PoC requires --confirm-desktop-upload.")

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.is_file() or file_path.stat().st_size <= 0:
        raise live.YandexUploadProtocolError("Selected owned upload file does not exist or is empty.")

    client = live._build_client(base_dir)  # noqa: SLF001
    playlist = live._resolve_playlist(client, args.playlist_kind)  # noqa: SLF001
    uid_value = getattr(playlist, "uid", None) or getattr(client, "account_uid", None)
    uid = str(uid_value or "").strip()
    if not uid:
        raise live.YandexUploadProtocolError("Unable to resolve authenticated playlist owner uid.")

    before_ids = live._playlist_track_ids(playlist)  # noqa: SLF001
    if not args.no_prompt:
        prompt(
            "In the already-authenticated official Yandex Music desktop client, "
            f"upload exactly one selected file into playlist kind {args.playlist_kind}, "
            "wait until the desktop UI finishes the upload, then press Enter here. "
        )

    def read_current_ids() -> set[str]:
        current = live._refresh_playlist(client, args.playlist_kind, uid)  # noqa: SLF001
        return live._playlist_track_ids(current)  # noqa: SLF001

    readback = verify_readback(
        before_ids=before_ids,
        read_current_ids=read_current_ids,
        attempts=args.readback_attempts,
        delay=args.readback_delay,
    )
    verified = bool(readback["verified"])
    payload = {
        "mode": "official-desktop-assisted",
        "transportMode": "official-desktop-assisted",
        "status": "verified" if verified else "uploaded_unverified",
        "mutation": {
            "initiatedByMusicArk": False,
            "expectedOfficialDesktopUpload": True,
            "singleFileOnly": True,
        },
        "playlist": {"kind": str(getattr(playlist, "kind", args.playlist_kind))},
        "file": live._file_summary(file_path),  # noqa: SLF001
        "readBack": readback,
    }
    return payload, (0 if verified else 3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify one normal official Yandex Music desktop upload through MusicArk playlist read-back."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--file", required=True)
    parser.add_argument("--playlist-kind", required=True)
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-desktop-upload", action="store_true")
    parser.add_argument("--readback-attempts", type=int, default=30)
    parser.add_argument("--readback-delay", type=float, default=2.0)
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip the Enter prompt only when the caller independently coordinates the visible official-client upload.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.readback_attempts < 1 or args.readback_attempts > 120:
        raise SystemExit("--readback-attempts must be between 1 and 120")
    if args.readback_delay < 0 or args.readback_delay > 10:
        raise SystemExit("--readback-delay must be between 0 and 10 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - safe CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
