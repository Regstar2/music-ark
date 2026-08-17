"""Real Yandex Music provider adapter."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

from musicark.core.errors import MusicArkError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.provider_storage import ProviderStorageRepository

from .base import MusicProvider
from .models import ProviderCapabilities, ProviderPlaylist, ProviderTrack
from .yandex_mapper import (
    map_track_source,
    map_yandex_album,
    map_yandex_playlist,
    map_yandex_track,
)


class YandexMusicError(MusicArkError):
    """Base error for Yandex provider operations."""


class YandexTokenMissingError(YandexMusicError):
    """Raised when Yandex token is missing."""


class YandexAuthenticationError(YandexMusicError):
    """Raised when Yandex token authentication fails."""


class YandexMusicProvider(MusicProvider):
    """Provider implementation that keeps yandex-music DTOs inside this module."""

    def __init__(self, base_dir: Path | None = None, token: str | None = None) -> None:
        self._base_dir = base_dir
        self._token = token.strip() if token else None

    @property
    def provider_id(self) -> str:
        return "yandex_music"

    @property
    def display_name(self) -> str:
        return "Yandex Music"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_authenticate=True,
            can_scan_library=True,
            can_scan_playlists=True,
            can_download_tracks=False,
            can_upload_tracks=False,
            can_create_playlists=False,
            can_edit_playlists=False,
            supports_track_availability=True,
            supports_user_uploads=False,
        )

    def health_check(self) -> dict[str, str]:
        self._build_client()
        return {"status": "ok", "provider": "yandex_music"}

    def list_tracks(self) -> list[ProviderTrack]:
        return [map_yandex_track(item) for item in self._fetch_liked_tracks_payload()]

    def list_playlists(self) -> list[ProviderPlaylist]:
        """Legacy eager playlist scan retained for provider-storage compatibility."""
        return [map_yandex_playlist(item) for item in self._fetch_playlists_payload()]

    def list_playlist_metadata(self) -> list[ProviderPlaylist]:
        """Return the user's playlist index without fetching each playlist's tracks."""
        return [map_yandex_playlist(item) for item in self._fetch_playlist_metadata_payload()]

    def list_liked_albums(self) -> list[dict[str, Any]]:
        """Return albums explicitly liked by the authenticated Yandex user."""
        client = self._build_client()
        try:
            method = getattr(client, "users_likes_albums", None)
            if not callable(method):
                raise YandexMusicError("Installed yandex-music client does not support liked albums.")
            result: list[dict[str, Any]] = []
            for like in method(rich=True) or []:
                like_payload = self._dto_payload(like)
                album_obj = getattr(like, "album", None)
                raw_album = self._dto_payload(album_obj) if album_obj is not None else {}
                if not raw_album and isinstance(like_payload.get("album"), dict):
                    raw_album = dict(like_payload["album"])
                if not raw_album:
                    continue
                liked_at = getattr(like, "timestamp", None) or like_payload.get("timestamp")
                mapped = map_yandex_album(raw_album, liked_at=liked_at)
                if mapped["externalId"]:
                    result.append(mapped)
            return result
        except YandexMusicError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError("Failed to scan liked Yandex albums.") from exc

    def get_album(self, external_id: str) -> tuple[dict[str, Any], list[ProviderTrack]]:
        """Fetch one Yandex album with its ordered tracks."""
        clean_id = external_id.strip()
        if not clean_id:
            raise YandexMusicError("Album external id is empty.")
        client = self._build_client()
        try:
            method = getattr(client, "albums_with_tracks", None)
            if not callable(method):
                raise YandexMusicError("Installed yandex-music client cannot load album tracks.")
            album_obj = method(clean_id)
            raw_album = self._dto_payload(album_obj)
            if not raw_album:
                raise YandexMusicError(f"Yandex album '{clean_id}' was not found.")
            track_payloads: list[dict[str, Any]] = []
            volumes = getattr(album_obj, "volumes", None)
            if volumes is None:
                volumes = raw_album.get("volumes") or []
            for volume in volumes or []:
                for item in volume or []:
                    payload = self._dto_payload(item)
                    if payload.get("id") is not None:
                        track_payloads.append(payload)
            return (
                map_yandex_album(raw_album),
                [map_yandex_track(item) for item in track_payloads],
            )
        except YandexMusicError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError(f"Failed to scan Yandex album '{clean_id}'.") from exc

    def get_playlist(self, external_id: str) -> tuple[ProviderPlaylist, list[ProviderTrack]]:
        """Fetch one playlist and map its ordered tracks across the provider boundary."""
        clean_id = external_id.strip()
        if not clean_id:
            raise YandexMusicError("Playlist external id is empty.")

        client = self._build_client()
        try:
            playlists = client.users_playlists_list() or []
            target = None
            for candidate in playlists:
                kind = getattr(candidate, "kind", None)
                if kind is not None and str(kind) == clean_id:
                    target = candidate
                    break
                candidate_dict = json.loads(candidate.to_json())
                if str(candidate_dict.get("kind", "")) == clean_id:
                    target = candidate
                    break
            if target is None:
                raise YandexMusicError(f"Yandex playlist '{clean_id}' was not found.")

            playlist_dict = json.loads(target.to_json())
            fetched_tracks = target.fetch_tracks() if hasattr(target, "fetch_tracks") else []
            track_payloads = self._hydrate_playlist_track_payloads(client, fetched_tracks)
            playlist_dict["track_refs"] = [
                str(item.get("id"))
                for item in track_payloads
                if item.get("id") is not None
            ]
            playlist_dict["track_count"] = len(track_payloads)
            return (
                map_yandex_playlist(playlist_dict),
                [map_yandex_track(item) for item in track_payloads],
            )
        except YandexMusicError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError(f"Failed to scan Yandex playlist '{clean_id}'.") from exc

    @staticmethod
    def _dto_payload(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return dict(item)
        raw = item.to_json() if hasattr(item, "to_json") else item
        if isinstance(raw, str):
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        return dict(raw) if isinstance(raw, dict) else {}

    def _hydrate_playlist_track_payloads(
        self,
        client: Any,
        fetched_tracks: Any,
    ) -> list[dict[str, Any]]:
        """Expand TrackShort playlist rows to full Track metadata with one batch request."""
        items = list(fetched_tracks or [])
        payloads: list[dict[str, Any]] = []
        request_ids: list[str] = []

        for item in items:
            embedded = getattr(item, "track", None)
            payload = self._dto_payload(embedded if embedded is not None else item)
            payloads.append(payload)
            if payload.get("title") and payload.get("artists"):
                continue
            external_id = payload.get("id") or getattr(item, "id", None)
            if external_id is None:
                continue
            request_id = str(getattr(item, "track_id", None) or external_id)
            if request_id not in request_ids:
                request_ids.append(request_id)

        if not request_ids:
            return payloads
        tracks_method = getattr(client, "tracks", None)
        if not callable(tracks_method):
            return payloads

        full_by_external_id: dict[str, dict[str, Any]] = {}
        for full_track in tracks_method(request_ids) or []:
            full_payload = self._dto_payload(full_track)
            external_id = full_payload.get("id")
            if external_id is not None:
                full_by_external_id[str(external_id)] = full_payload

        hydrated: list[dict[str, Any]] = []
        for payload in payloads:
            external_id = payload.get("id")
            if external_id is None:
                hydrated.append(payload)
                continue
            hydrated.append(full_by_external_id.get(str(external_id), payload))
        return hydrated

    def auth_check(self) -> dict[str, Any]:
        client = self._build_client()
        try:
            account = client.me.account.to_dict()
        except Exception as exc:  # noqa: BLE001
            raise YandexAuthenticationError("Yandex auth-check failed.") from exc
        return {
            "provider": "yandex_music",
            "providerUserId": str(account.get("uid", "")),
            "displayName": account.get("display_name") or account.get("login") or "",
        }

    def scan_all(self, database_path: Path) -> dict[str, Any]:
        scanned_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        account = self.auth_check()
        tracks_payload = self._fetch_liked_tracks_payload()
        playlists_payload = self._fetch_playlists_payload()
        tracks = [map_yandex_track(item) for item in tracks_payload]
        playlists = [map_yandex_playlist(item) for item in playlists_payload]
        track_sources = [map_track_source(track) for track in tracks]

        storage = ProviderStorageRepository(database_path)
        storage.upsert_provider(self, metadata={"last_scanned_at": scanned_at})
        for track in tracks:
            storage.upsert_provider_track(track)
        for playlist in playlists:
            storage.upsert_provider_playlist(playlist)
        for source in track_sources:
            storage.upsert_track_source(source)

        raw_storage_payload = {
            "schemaVersion": 1,
            "provider": "yandex_music",
            "scannedAt": scanned_at,
            "account": account,
            "likedTracks": tracks_payload,
            "playlists": playlists_payload,
            "rawResponses": [
                {"type": "account", "payload": account},
                {"type": "liked_tracks", "payload": tracks_payload},
                {"type": "playlists", "payload": playlists_payload},
            ],
        }
        storage.insert_raw_response("yandex_music", "scan_all", raw_storage_payload)
        AuditLogRepository(database_path).append(
            AuditEvent(
                event_type="provider_scan",
                entity_type="provider",
                entity_id="yandex_music",
                status="success",
                details=f"scan_all tracks={len(tracks)} playlists={len(playlists)}",
            )
        )
        return {
            "schemaVersion": 1,
            "provider": "yandex_music",
            "scannedAt": scanned_at,
            "account": account,
            "likedTracks": [asdict(track) for track in tracks],
            "playlists": [asdict(playlist) for playlist in playlists],
            "rawResponses": [
                {"type": "account", "count": 1},
                {"type": "liked_tracks", "count": len(tracks_payload)},
                {"type": "playlists", "count": len(playlists_payload)},
            ],
        }

    def _resolve_token(self) -> str:
        if self._token:
            return self._token
        token = os.getenv("YANDEX_MUSIC_TOKEN", "").strip()
        if token:
            return token
        if self._base_dir is not None:
            local_properties = self._base_dir / "local.properties"
            if local_properties.exists():
                for line in local_properties.read_text(encoding="utf-8").splitlines():
                    if line.startswith("YANDEX_MUSIC_TOKEN="):
                        local_token = line.split("=", 1)[1].strip()
                        if local_token:
                            return local_token
        raise YandexTokenMissingError("YANDEX_MUSIC_TOKEN is not configured.")

    def _build_client(self):  # type: ignore[no-untyped-def]
        token = self._resolve_token()
        try:
            from yandex_music import Client  # type: ignore
        except ImportError as exc:
            raise YandexMusicError(
                "yandex-music dependency is missing. Install requirements-yandex.txt."
            ) from exc
        try:
            return Client(token).init()
        except Exception as exc:  # noqa: BLE001
            raise YandexAuthenticationError("Failed to initialize Yandex client.") from exc

    def _fetch_liked_tracks_payload(self) -> list[dict]:
        client = self._build_client()
        try:
            liked = client.users_likes_tracks()
            short_tracks = liked.fetch_tracks() if liked is not None else []
            return [json.loads(item.to_json()) for item in (short_tracks or [])]
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError("Failed to scan liked tracks.") from exc

    def _fetch_playlist_metadata_payload(self) -> list[dict]:
        client = self._build_client()
        try:
            playlists = client.users_playlists_list() or []
            return [json.loads(playlist.to_json()) for playlist in playlists]
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError("Failed to scan playlist metadata.") from exc

    def _fetch_playlists_payload(self) -> list[dict]:
        client = self._build_client()
        try:
            playlists = client.users_playlists_list() or []
            payload: list[dict] = []
            for playlist in playlists:
                playlist_dict = json.loads(playlist.to_json())
                tracks = playlist.fetch_tracks() if hasattr(playlist, "fetch_tracks") else []
                playlist_dict["track_refs"] = [
                    str(item.id) for item in tracks if getattr(item, "id", None) is not None
                ]
                payload.append(playlist_dict)
            return payload
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError("Failed to scan playlists.") from exc
