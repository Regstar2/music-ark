#!/usr/bin/env python3
"""Manual live proof for pinned yandex-music playlist mutation APIs.

This utility is intentionally excluded from CI.  It performs real Yandex
mutations only when MUSICARK_YANDEX_PLAYLIST_LIVE=1 is present.  Output is
sanitized: no token, UID, cookies, headers, raw response or signed URL is ever
serialized.
"""

from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

from musicark.core.config import load_config
from musicark.credentials import SystemCredentialStore

_TEST_TITLE = "MusicArk v0.11.1 TEST"


def _safe_http_status(exc: BaseException) -> int | None:
    for name in ("status_code", "status", "code"):
        value = getattr(exc, name, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) and 100 <= value <= 599 else None


def _result(method: str, *, success: bool, **extra: Any) -> dict[str, Any]:
    return {"method": method, "success": bool(success), **extra}


def _failed(method: str, exc: BaseException) -> dict[str, Any]:
    return _result(
        method,
        success=False,
        exceptionClass=type(exc).__name__,
        httpStatus=_safe_http_status(exc),
    )


def _database_path(base_dir: Path) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    return raw if raw.is_absolute() else base_dir / raw


def _cached_unavailable_fixture(database_path: Path) -> dict[str, str] | None:
    """Return only a real cached unavailable provider identity, never a guessed ID."""
    if not database_path.exists():
        return None
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            rows = conn.execute(
                """
                SELECT i.payload_json
                FROM provider_collection_snapshots s
                JOIN provider_collection_items i
                  ON i.provider_id=s.provider_id AND i.collection_id=s.collection_id
                WHERE s.provider_id='yandex_music'
                  AND s.collection_type='playlist'
                  AND s.active=1
                """
            ).fetchall()
    except sqlite3.Error:
        return None
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("availability") != "unavailable":
            continue
        track_id = str(payload.get("external_id") or payload.get("externalId") or "").strip()
        album_id = str(
            payload.get("album_external_id") or payload.get("albumExternalId") or ""
        ).strip()
        if track_id and album_id:
            return {"trackId": track_id, "albumId": album_id}
    return None


def _track_id(item: Any) -> str:
    value = getattr(item, "id", None)
    if value is None:
        embedded = getattr(item, "track", None)
        value = getattr(embedded, "id", None) if embedded is not None else None
    return str(value or "").strip()


def _playlist_membership(playlist: Any) -> set[str]:
    tracks = playlist.fetch_tracks() if hasattr(playlist, "fetch_tracks") else []
    return {value for item in (tracks or []) if (value := _track_id(item))}


def _available_fixture(client: Any) -> dict[str, str] | None:
    likes = client.users_likes_tracks()
    shorts = likes.fetch_tracks() if likes is not None and hasattr(likes, "fetch_tracks") else list(likes or [])
    for short in shorts or []:
        full = getattr(short, "track", None)
        if full is None:
            fetch_track = getattr(short, "fetch_track", None)
            if callable(fetch_track):
                try:
                    full = fetch_track()
                except Exception:  # noqa: BLE001 - research fixture discovery continues
                    full = None
        if full is None:
            continue
        if getattr(full, "available", None) is False:
            continue
        track_id = str(getattr(full, "id", "") or "").strip()
        albums = list(getattr(full, "albums", None) or [])
        album_id = str(getattr(albums[0], "id", "") or "").strip() if albums else ""
        if track_id and album_id:
            return {"trackId": track_id, "albumId": album_id}
    return None


def main() -> int:
    if os.getenv("MUSICARK_YANDEX_PLAYLIST_LIVE", "").strip() != "1":
        print(
            json.dumps(
                {
                    "live": False,
                    "error": "live_opt_in_required",
                    "requiredFlag": "MUSICARK_YANDEX_PLAYLIST_LIVE=1",
                },
                ensure_ascii=False,
            )
        )
        return 2

    token = None
    try:
        token = SystemCredentialStore().get_token()
    except Exception:  # noqa: BLE001 - explicit env fallback is acceptable for this manual tool
        token = None
    token = token or os.getenv("YANDEX_MUSIC_TOKEN", "").strip() or None
    if not token:
        print(json.dumps({"live": True, "error": "yandex_auth_required"}))
        return 2

    try:
        from yandex_music import Client

        client = Client(token).init()
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"live": True, "error": "client_init_failed", "exceptionClass": type(exc).__name__}
            )
        )
        return 2

    base_dir = Path(__file__).resolve().parents[1]
    report: dict[str, Any] = {
        "live": True,
        "dependency": "yandex-music==3.0.0",
        "testPlaylistTitle": _TEST_TITLE,
        "steps": [],
        "canCreatePlaylists": False,
        "canInsertAvailableTrack": False,
        "canInsertUnavailableProviderTrack": "not_tested_no_fixture",
        "cleanup": "not_needed",
    }
    created: Any = None

    try:
        # A. Establish that revision is present on an owned playlist snapshot.
        try:
            existing = list(client.users_playlists_list() or [])
            revision = getattr(existing[0], "revision", None) if existing else None
            report["steps"].append(
                _result(
                    "users_playlists_list/revision",
                    success=revision is not None or not existing,
                    revisionPresent=revision is not None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            report["steps"].append(_failed("users_playlists_list/revision", exc))

        # B/C. Create PRIVATE test playlist and read it back.
        try:
            created = client.users_playlists_create(_TEST_TITLE, visibility="private")
            kind = str(getattr(created, "kind", "") or "").strip()
            if not kind:
                raise RuntimeError("created_playlist_without_kind")
            report["steps"].append(
                _result("users_playlists_create", success=True, playlistKind=kind, visibility="private")
            )
            report["canCreatePlaylists"] = True
            read_back = client.users_playlists(kind)
            read_back_kind = str(getattr(read_back, "kind", "") or "").strip()
            report["steps"].append(
                _result(
                    "users_playlists/read_back",
                    success=read_back_kind == kind,
                    playlistKind=kind,
                    revisionPresent=getattr(read_back, "revision", None) is not None,
                )
            )
            created = read_back
        except Exception as exc:  # noqa: BLE001
            report["steps"].append(_failed("users_playlists_create/read_back", exc))
            return_code = 1
            return return_code

        kind = str(getattr(created, "kind", "") or "").strip()

        # D/E. Insert one real, currently available Yandex track and verify membership.
        fixture = _available_fixture(client)
        if fixture is None:
            report["steps"].append(
                _result("users_playlists_insert_track/available", success=False, state="not_tested_no_fixture")
            )
        else:
            try:
                revision = int(getattr(created, "revision", 1) or 1)
                changed = client.users_playlists_insert_track(
                    kind,
                    fixture["trackId"],
                    fixture["albumId"],
                    at=int(getattr(created, "track_count", 0) or 0),
                    revision=revision,
                )
                if changed is not None:
                    created = changed
                refreshed = client.users_playlists(kind)
                present = fixture["trackId"] in _playlist_membership(refreshed)
                report["steps"].append(
                    _result(
                        "users_playlists_insert_track/available",
                        success=present,
                        playlistKind=kind,
                        trackId=fixture["trackId"],
                    )
                )
                report["canInsertAvailableTrack"] = bool(present)
                created = refreshed
            except Exception as exc:  # noqa: BLE001
                report["steps"].append(_failed("users_playlists_insert_track/available", exc))

        # G. Only a real cached unavailable identity may be used as a fixture.
        unavailable = _cached_unavailable_fixture(_database_path(base_dir))
        if unavailable is not None:
            try:
                refreshed = client.users_playlists(kind)
                revision = int(getattr(refreshed, "revision", 1) or 1)
                changed = client.users_playlists_insert_track(
                    kind,
                    unavailable["trackId"],
                    unavailable["albumId"],
                    at=int(getattr(refreshed, "track_count", 0) or 0),
                    revision=revision,
                )
                refreshed = changed or client.users_playlists(kind)
                present = unavailable["trackId"] in _playlist_membership(refreshed)
                report["steps"].append(
                    _result(
                        "users_playlists_insert_track/unavailable",
                        success=present,
                        playlistKind=kind,
                        trackId=unavailable["trackId"],
                    )
                )
                report["canInsertUnavailableProviderTrack"] = bool(present)
            except Exception as exc:  # noqa: BLE001
                report["steps"].append(_failed("users_playlists_insert_track/unavailable", exc))
                report["canInsertUnavailableProviderTrack"] = False
        else:
            report["steps"].append(
                _result(
                    "users_playlists_insert_track/unavailable",
                    success=False,
                    state="not_tested_no_fixture",
                )
            )
    finally:
        if created is not None:
            kind = str(getattr(created, "kind", "") or "").strip()
            if kind:
                try:
                    cleaned = bool(client.users_playlists_delete(kind))
                    report["cleanup"] = "success" if cleaned else "failed"
                    report["steps"].append(
                        _result("users_playlists_delete", success=cleaned, playlistKind=kind)
                    )
                except Exception as exc:  # noqa: BLE001
                    report["cleanup"] = "failed"
                    report["steps"].append(_failed("users_playlists_delete", exc))

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["canCreatePlaylists"] and report["cleanup"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
