"""Run one Stage1-only Chromium differential with the recovered playlist-id formula.

Official desktop static ground truth resolves ``playlist-id`` as
``<uid>:<playlistKind>``. This probe changes only that query value relative to
the previous cached-UUID + filename-only differential. It remains no-auth,
uses renderer Accept-Language, omits browser credentials, sends Stage1 only,
never follows the upload target, and never emits uid/query/header values or
audio bytes.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import yandex_upload_cdp_path_name_probe as path_probe


_FORMAT = "musicark-yandex-upload-cdp-composite-playlist-id-differential-v1"
_SOURCE = "uid-colon-kind-static-ground-truth"
_ORIGINAL_CONTEXT = path_probe.uuid_probe.language.noauth.base._cached_stage1_context  # noqa: SLF001


def _composite_context(args: Any, base_dir):  # noqa: ANN001, ANN201
    base = path_probe.uuid_probe.language.noauth.base
    context = _ORIGINAL_CONTEXT(args, base_dir)
    playlist_kind = str(args.playlist_kind or "").strip()
    if not playlist_kind:
        raise base.YandexUploadProtocolError("Playlist kind is empty.")
    if str(args.playlist_id_source or "").strip().lower() != "uuid":
        raise base.YandexUploadProtocolError(
            "Composite playlist-id differential requires --playlist-id-source uuid to preserve the previous baseline."
        )
    return base._CachedStage1Context(  # noqa: SLF001
        file_path=context.file_path,
        uid=context.uid,
        playlist_id=f"{context.uid}:{playlist_kind}",
        playlist_id_source=_SOURCE,
        playlist_id_fallback=False,
        observed_visibility=context.observed_visibility,
    )


def run(args: Any) -> tuple[dict[str, Any], int]:
    if str(args.path_mode or "").strip().lower() != "name":
        raise path_probe.uuid_probe.language.noauth.base.YandexUploadProtocolError(  # noqa: SLF001
            "Composite playlist-id differential requires --path-mode name."
        )

    original_uuid_context = path_probe.uuid_probe._uuid_context  # noqa: SLF001
    path_probe.uuid_probe._uuid_context = _composite_context  # noqa: SLF001
    try:
        payload, code = path_probe.run(args)
    finally:
        path_probe.uuid_probe._uuid_context = original_uuid_context  # noqa: SLF001

    payload["format"] = _FORMAT
    playlist = payload.get("playlist") if isinstance(payload.get("playlist"), dict) else {}
    playlist["playlistIdSourceUsed"] = _SOURCE
    playlist["playlistIdDiagnosticFallback"] = False
    playlist["playlistIdFormula"] = "uid:playlistKind"
    payload["playlist"] = playlist

    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    probe["differentialVariable"] = "playlist-id-cached-uuid-to-uid-colon-kind"
    probe["formulaEvidence"] = "official-desktop-asar-v46-v47"
    payload["probe"] = probe

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    safety.update(
        {
            "playlist_composite_value_included": False,
            "playlist_id_formula_contains_secret": False,
            "playlist_uuid_value_included": False,
            "playlist_kind_fallback_allowed": False,
            "authorization_header_sent": False,
            "audio_bytes_sent": False,
        }
    )
    payload["safety"] = safety
    return payload, code


def main() -> int:
    parser = path_probe.uuid_probe.language.noauth.base.build_parser()
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
