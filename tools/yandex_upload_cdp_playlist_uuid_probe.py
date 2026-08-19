"""Run the Chromium language differential with an exact cached playlist UUID.

This diagnostic changes one variable relative to
``yandex_upload_cdp_language_probe``: ``playlist-id`` must come from the
provider-specific playlist UUID cached by MusicArk instead of the numeric
playlist kind diagnostic fallback.

The tool remains no-auth, uses ``credentials: 'omit'``, sends stage one only,
and never returns the UUID value, query values, credentials, response bodies,
request IDs, signed URLs, or audio bytes. It fails closed before Chromium
network activity when the UUID is unavailable so a kind fallback cannot hide a
protocol mismatch.
"""

from __future__ import annotations

import json
from contextlib import closing
import sqlite3
import sys
from typing import Any

import yandex_upload_cdp_language_probe as language


_FORMAT = "musicark-yandex-upload-cdp-playlist-uuid-differential-v1"
_PROVIDER_ID = "yandex_music"
_ORIGINAL_CONTEXT = language.noauth.base._cached_stage1_context  # noqa: SLF001


def _cached_playlist_uuid(args: Any, base_dir) -> str | None:  # noqa: ANN001
    playlist_kind = str(args.playlist_kind or "").strip()
    if not playlist_kind:
        return None
    database_path = language.noauth.base._resolve_database_path(base_dir)  # noqa: SLF001
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            row = conn.execute(
                """
                SELECT metadata_json
                FROM provider_collection_snapshots
                WHERE provider_id=? AND collection_id=?
                  AND collection_type='playlist' AND active=1
                LIMIT 1
                """,
                (_PROVIDER_ID, f"playlist:{playlist_kind}"),
            ).fetchone()
    except sqlite3.Error as exc:
        raise language.noauth.base.YandexUploadProtocolError(  # noqa: SLF001
            f"Failed to read cached playlist UUID ({type(exc).__name__})."
        ) from exc
    if not row:
        return None
    try:
        metadata = json.loads(row[0]) if row[0] else {}
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    return language.noauth.base._playlist_uuid_from_payload(metadata)  # noqa: SLF001


def _uuid_context(args: Any, base_dir):  # noqa: ANN001, ANN201
    context = _ORIGINAL_CONTEXT(args, base_dir)
    requested_source = str(args.playlist_id_source or "uuid").strip().lower()
    if requested_source != "uuid":
        raise language.noauth.base.YandexUploadProtocolError(  # noqa: SLF001
            "Playlist UUID differential requires --playlist-id-source uuid."
        )

    playlist_uuid = _cached_playlist_uuid(args, base_dir)
    if not playlist_uuid:
        raise language.noauth.base.YandexUploadProtocolError(  # noqa: SLF001
            "Cached Yandex playlist UUID is unavailable; refresh the Yandex library index before this probe."
        )

    return language.noauth.base._CachedStage1Context(  # noqa: SLF001
        file_path=context.file_path,
        uid=context.uid,
        playlist_id=playlist_uuid,
        playlist_id_source="uuid-cache-metadata",
        playlist_id_fallback=False,
        observed_visibility=context.observed_visibility,
    )


def run(args: Any) -> tuple[dict[str, Any], int]:
    base = language.noauth.base
    original_context = base._cached_stage1_context  # noqa: SLF001
    base._cached_stage1_context = _uuid_context  # noqa: SLF001
    try:
        payload, code = language.run(args)
    finally:
        base._cached_stage1_context = original_context  # noqa: SLF001

    payload["format"] = _FORMAT
    playlist = payload.get("playlist") if isinstance(payload.get("playlist"), dict) else {}
    playlist["playlistIdSourceUsed"] = "uuid-cache-metadata"
    playlist["playlistIdDiagnosticFallback"] = False
    payload["playlist"] = playlist

    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    probe["differentialVariable"] = "playlist-id-kind-to-cached-uuid"
    payload["probe"] = probe

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    safety.update(
        {
            "playlist_uuid_value_included": False,
            "playlist_kind_fallback_allowed": False,
        }
    )
    payload["safety"] = safety
    return payload, code


def main() -> int:
    parser = language.noauth.base.build_parser()
    args = parser.parse_args()
    if args.launch_wait < 0 or args.launch_wait > 60:
        raise SystemExit("--launch-wait must be between 0 and 60 seconds")
    if args.timeout <= 0 or args.timeout > 120:
        raise SystemExit("--timeout must be between 0 and 120 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - safe CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
