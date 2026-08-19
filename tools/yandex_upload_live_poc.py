"""Explicit local runner for the experimental Yandex own-track upload PoC.

The runner is intentionally separate from MusicArk Sync/UI. It never accepts a
Yandex token on the command line, never prints the token or dynamic upload URLs,
and requires explicit opt-in before any network mutation.

The official desktop runtime has verified ``https://api.music.yandex.net`` as the
stage-one origin and observed a stage-one response containing ``post-target``,
``poll-result`` and ``ugc-track-id``. Direct HTTP still requires an explicit
``--stage1-base-url`` so normal MusicArk behavior remains fail-closed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from musicark.core.config import load_config
from musicark.credentials import CredentialStoreError, SystemCredentialStore
from musicark.providers.yandex_music_provider import YandexMusicProvider, YandexTokenMissingError
from musicark.providers.yandex_upload_transport import (
    YandexOAuthStage1Requester,
    YandexUploadProtocolError,
    YandexUploadTransport,
)


_TRUE = {"1", "true", "yes", "on"}


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUE


def _require_research_opt_in(base_dir: Path | None) -> None:
    config_enabled = bool(load_config(base_dir).experimental_yandex_upload)
    env_enabled = _enabled(os.getenv("MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD"))
    if not (config_enabled or env_enabled):
        raise YandexUploadProtocolError(
            "Experimental upload is disabled. Enable the MusicArk experimental Yandex upload flag first."
        )


def _saved_token(base_dir: Path | None) -> str:
    """Resolve the already-saved MusicArk token without accepting CLI secrets."""
    try:
        token = SystemCredentialStore().get_token()
    except CredentialStoreError:
        token = None
    if token:
        return token

    provider = YandexMusicProvider(base_dir=base_dir)
    try:
        return provider._resolve_token()  # noqa: SLF001 - existing credential boundary fallback.
    except YandexTokenMissingError:
        raise YandexTokenMissingError(
            "No saved Yandex token is available in the MusicArk credential boundary."
        ) from None


def _build_client(base_dir: Path | None) -> Any:
    token = _saved_token(base_dir)
    return YandexMusicProvider(base_dir=base_dir, token=token)._build_client()  # noqa: SLF001


def _resolve_playlist(client: Any, kind: str) -> Any:
    method = getattr(client, "users_playlists_list", None)
    if not callable(method):
        raise YandexUploadProtocolError("Yandex client cannot list user playlists.")
    for playlist in method() or []:
        if str(getattr(playlist, "kind", "")) == str(kind):
            return playlist
    raise YandexUploadProtocolError(f"User playlist kind '{kind}' was not found.")


def _playlist_track_ids(playlist: Any) -> set[str]:
    tracks = playlist.fetch_tracks() if hasattr(playlist, "fetch_tracks") else []
    result: set[str] = set()
    for item in tracks or []:
        value = getattr(item, "id", None)
        embedded = getattr(item, "track", None)
        if value is None and embedded is not None:
            value = getattr(embedded, "id", None)
        if value is not None and str(value).strip():
            result.add(str(value).strip())
    return result


def _upload_playlist_id(playlist: Any, source: str) -> str:
    value = getattr(playlist, "kind", None) if source == "kind" else getattr(playlist, "playlist_uuid", None)
    clean = str(value or "").strip()
    if not clean:
        raise YandexUploadProtocolError(f"Playlist has no usable {source} identifier for the upload request.")
    return clean


def _refresh_playlist(client: Any, kind: str, uid: str) -> Any:
    method = getattr(client, "users_playlists", None)
    if not callable(method):
        raise YandexUploadProtocolError("Yandex client cannot read back a playlist.")
    playlist = method(kind, uid)
    if playlist is None:
        raise YandexUploadProtocolError("Yandex playlist read-back returned no playlist.")
    return playlist


def _file_summary(path: Path) -> dict[str, Any]:
    return {"name": path.name, "extension": path.suffix.lower(), "size": path.stat().st_size}


def _classify_readback_identity(
    before_ids: set[str],
    current_ids: set[str],
    reported_track_id: str | None,
) -> dict[str, Any]:
    """Require an unambiguous new track identity before declaring success."""
    new_ids = current_ids - before_ids
    clean_reported = str(reported_track_id or "").strip() or None
    if clean_reported and clean_reported in new_ids:
        return {
            "verified": True,
            "newTrackIds": sorted(new_ids),
            "verifiedTrackId": clean_reported,
            "identitySource": "reported-track-id",
            "ambiguous": False,
        }
    if len(new_ids) == 1:
        only = next(iter(new_ids))
        return {
            "verified": True,
            "newTrackIds": [only],
            "verifiedTrackId": only,
            "identitySource": "single-readback-difference",
            "ambiguous": False,
        }
    if len(new_ids) > 1:
        return {
            "verified": False,
            "newTrackIds": sorted(new_ids),
            "verifiedTrackId": None,
            "identitySource": "ambiguous-readback-difference",
            "ambiguous": True,
        }
    return {
        "verified": False,
        "newTrackIds": [],
        "verifiedTrackId": None,
        "identitySource": "not-observed",
        "ambiguous": False,
    }


def _prepare_context(args: argparse.Namespace) -> tuple[Any, Any, Path, str, str, str | None]:
    base_dir = Path(args.base_dir) if args.base_dir else None
    _require_research_opt_in(base_dir)
    if not args.confirm_owned_file:
        raise YandexUploadProtocolError(
            "Refusing to continue without --confirm-owned-file for the explicitly selected local file."
        )

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.is_file():
        raise YandexUploadProtocolError("Selected upload file does not exist.")
    if file_path.stat().st_size <= 0:
        raise YandexUploadProtocolError("Selected upload file is empty.")

    client = _build_client(base_dir)
    playlist = _resolve_playlist(client, args.playlist_kind)
    uid_value = getattr(playlist, "uid", None) or getattr(client, "account_uid", None)
    uid = str(uid_value or "").strip()
    if not uid:
        raise YandexUploadProtocolError("Unable to resolve the authenticated playlist owner uid.")

    playlist_id = _upload_playlist_id(playlist, args.playlist_id_source)
    visibility_value = getattr(playlist, "visibility", None)
    visibility = str(visibility_value).strip() if visibility_value else None
    return client, playlist, file_path, uid, playlist_id, visibility


def _stage1_path(file_path: Path, mode: str) -> str:
    return file_path.name if mode == "name" else str(file_path)


def _live_transport(
    base_dir: Path | None = None,
    stage1_base_url: str | None = None,
    *,
    transport_mode: str = "requests",
    client_profile: str = "bare",
    trust_env: bool = True,
) -> YandexUploadTransport:
    """Build a fail-closed transport or one explicit evidence-backed requester."""
    clean_base_url = str(stage1_base_url or "").strip()
    if not clean_base_url:
        return YandexUploadTransport()
    requester = YandexOAuthStage1Requester(
        base_url=clean_base_url,
        oauth_token=_saved_token(base_dir),
        transport_mode=transport_mode,
        client_profile=client_profile,
        trust_env=trust_env,
    )
    return YandexUploadTransport(requester)


def _base_dir_from_args(args: argparse.Namespace) -> Path | None:
    value = getattr(args, "base_dir", None)
    return Path(value) if value else None


def _transport_from_args(args: argparse.Namespace, base_dir: Path | None) -> YandexUploadTransport:
    return _live_transport(
        base_dir,
        getattr(args, "stage1_base_url", None),
        transport_mode=getattr(args, "stage1_transport", "requests"),
        client_profile=getattr(args, "stage1_client_profile", "bare"),
        trust_env=not bool(getattr(args, "stage1_ignore_env", False)),
    )


def run_prepare(args: argparse.Namespace) -> dict[str, Any]:
    if not args.confirm_prepare:
        raise YandexUploadProtocolError("prepare mode requires --confirm-prepare.")

    base_dir = _base_dir_from_args(args)
    transport = _transport_from_args(args, base_dir)
    transport.require_stage1_profile()

    _client, playlist, file_path, uid, playlist_id, observed_visibility = _prepare_context(args)
    # The verified desktop stage-one trace contained uid, playlist-id and path,
    # but no visibility query parameter. Direct experiments therefore follow the
    # observed request instead of adding the statically optional parameter.
    slot = transport.prepare_upload(
        uid=uid,
        playlist_id=playlist_id,
        visibility=None,
        path=_stage1_path(file_path, args.path_mode),
    )
    return {
        "mode": "prepare",
        "status": "upload_url_obtained",
        "network": {"stage1Sent": True, "stage2Sent": False},
        "playlist": {
            "kind": str(getattr(playlist, "kind", "")),
            "playlistIdSource": args.playlist_id_source,
            "observedVisibility": observed_visibility,
        },
        "file": _file_summary(file_path),
        "stage1": {
            "uploadUrlPresent": bool(slot.upload_url),
            "pollUrlPresent": bool(slot.poll_url),
            "trackIdPresent": bool(slot.track_id),
            "visibilitySent": False,
            "requestProfile": transport.stage1_profile,
            "responseShape": slot.response_shape,
        },
    }


def run_upload(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if not args.confirm_upload:
        raise YandexUploadProtocolError("upload mode requires --confirm-upload.")
    if not _enabled(os.getenv("MUSICARK_YANDEX_UPLOAD_LIVE")):
        raise YandexUploadProtocolError(
            "Live mutation is disabled. Set MUSICARK_YANDEX_UPLOAD_LIVE=1 for this explicit local PoC."
        )

    base_dir = _base_dir_from_args(args)
    transport = _transport_from_args(args, base_dir)
    transport.require_stage1_profile()

    client, playlist, file_path, uid, playlist_id, observed_visibility = _prepare_context(args)
    before_ids = _playlist_track_ids(playlist)
    slot = transport.prepare_upload(
        uid=uid,
        playlist_id=playlist_id,
        visibility=None,
        path=_stage1_path(file_path, args.path_mode),
    )
    transfer = transport.upload_file(slot, file_path)
    reported_track_id = transfer.track_id or slot.track_id

    attempts_used = 0
    readback = _classify_readback_identity(before_ids, before_ids, reported_track_id)
    for attempt in range(1, args.readback_attempts + 1):
        attempts_used = attempt
        current = _refresh_playlist(client, args.playlist_kind, uid)
        current_ids = _playlist_track_ids(current)
        readback = _classify_readback_identity(before_ids, current_ids, reported_track_id)
        if readback["verified"] or readback["ambiguous"]:
            break
        if attempt < args.readback_attempts:
            time.sleep(args.readback_delay)

    verified = bool(readback["verified"])
    payload = {
        "mode": "upload",
        "status": "verified" if verified else "uploaded_unverified",
        "network": {"stage1Sent": True, "stage2Sent": True, "readBackSent": True},
        "playlist": {
            "kind": str(getattr(playlist, "kind", "")),
            "playlistIdSource": args.playlist_id_source,
            "observedVisibility": observed_visibility,
        },
        "file": _file_summary(file_path),
        "stage1": {
            "uploadUrlPresent": bool(slot.upload_url),
            "pollUrlPresent": bool(slot.poll_url),
            "trackIdPresent": bool(slot.track_id),
            "visibilitySent": False,
            "requestProfile": transport.stage1_profile,
            "responseShape": slot.response_shape,
        },
        "stage2": {
            "httpStatus": transfer.status_code,
            "responseShape": transfer.response_shape,
            "trackIdPresent": transfer.track_id is not None,
        },
        "readBack": {**readback, "attemptsUsed": attempts_used},
    }
    return payload, (0 if verified else 3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explicit local PoC for the recovered Yandex Music own-track upload transport."
    )
    parser.add_argument("mode", choices=("prepare", "upload"))
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--file", required=True, help="Explicit local audio file owned/authorized by the user.")
    parser.add_argument("--playlist-kind", required=True, help="Existing user playlist kind used for read-back.")
    parser.add_argument(
        "--stage1-base-url",
        default=None,
        help="Explicit ground-truth-verified HTTPS Yandex stage-one prefix. No default or fallback is used.",
    )
    parser.add_argument(
        "--stage1-transport",
        choices=("requests", "http2"),
        default="requests",
        help="Explicit stage-one HTTP stack. http2 uses HTTPX with HTTP/2 enabled; no automatic fallback occurs.",
    )
    parser.add_argument(
        "--stage1-client-profile",
        choices=("bare", "desktop"),
        default="bare",
        help="Public request-header profile. desktop adds only X-Yandex-Music-Client: YandexMusicDesktopApp.",
    )
    parser.add_argument(
        "--stage1-ignore-env",
        action="store_true",
        help="Ignore proxy/SSL environment configuration for the stage-one request only.",
    )
    parser.add_argument(
        "--playlist-id-source",
        choices=("uuid", "kind"),
        default="uuid",
        help="Which playlist identifier is sent as the recovered playlist-id field.",
    )
    parser.add_argument(
        "--path-mode",
        choices=("full", "name"),
        default="full",
        help="Value used for the recovered stage-one path field.",
    )
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-prepare", action="store_true")
    parser.add_argument("--confirm-upload", action="store_true")
    parser.add_argument("--readback-attempts", type=int, default=15)
    parser.add_argument("--readback-delay", type=float, default=2.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.readback_attempts < 1 or args.readback_attempts > 60:
        raise SystemExit("--readback-attempts must be between 1 and 60")
    if args.readback_delay < 0 or args.readback_delay > 10:
        raise SystemExit("--readback-delay must be between 0 and 10 seconds")

    try:
        if args.mode == "prepare":
            payload = run_prepare(args)
            code = 0
        else:
            payload, code = run_upload(args)
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns a safe error.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
