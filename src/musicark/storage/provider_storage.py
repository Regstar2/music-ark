"""SQLite persistence helpers for provider registry metadata."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.providers.models import ProviderPlaylist, ProviderTrack, TrackSource


class ProviderStorageRepository:
    """Persists provider declarations and track-source metadata."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def upsert_provider(
        self, provider: Any, metadata: dict[str, Any] | None = None
    ) -> None:
        capabilities_json = json.dumps(asdict(provider.capabilities), ensure_ascii=False)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO providers(
                            provider_id, display_name, capabilities_json, metadata_json
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT(provider_id) DO UPDATE SET
                            display_name=excluded.display_name,
                            capabilities_json=excluded.capabilities_json,
                            metadata_json=excluded.metadata_json,
                            updated_at=datetime('now')
                        """,
                        (
                            provider.provider_id,
                            provider.display_name,
                            capabilities_json,
                            metadata_json,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist provider metadata.") from exc

    def upsert_track_source(self, track_source: TrackSource) -> None:
        raw_data_json = json.dumps(track_source.raw_data, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO track_sources(
                            track_id, source_type, provider_id, external_id, url, availability, raw_data_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            track_id=excluded.track_id,
                            source_type=excluded.source_type,
                            url=excluded.url,
                            availability=excluded.availability,
                            raw_data_json=excluded.raw_data_json,
                            last_seen_at=datetime('now')
                        """,
                        (
                            track_source.track_id,
                            track_source.source_type,
                            track_source.provider_id,
                            track_source.external_id,
                            track_source.url,
                            track_source.availability,
                            raw_data_json,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist track source metadata.") from exc

    def upsert_provider_track(self, track: ProviderTrack) -> None:
        payload_json = json.dumps(asdict(track), ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_tracks(provider_id, external_id, payload_json)
                        VALUES (?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            payload_json=excluded.payload_json,
                            updated_at=datetime('now')
                        """,
                        (track.provider_id, track.external_id, payload_json),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist provider track.") from exc

    def upsert_provider_playlist(self, playlist: ProviderPlaylist) -> None:
        payload_json = json.dumps(asdict(playlist), ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_playlists(provider_id, external_id, payload_json)
                        VALUES (?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            payload_json=excluded.payload_json,
                            updated_at=datetime('now')
                        """,
                        (playlist.provider_id, playlist.external_id, payload_json),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist provider playlist.") from exc

    def insert_raw_response(
        self, provider_id: str, response_type: str, payload: dict[str, Any]
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_raw_responses(provider_id, response_type, payload_json)
                        VALUES (?, ?, ?)
                        """,
                        (provider_id, response_type, payload_json),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist raw provider response.") from exc
