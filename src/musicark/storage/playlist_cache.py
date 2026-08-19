"""SQLite cache for Yandex playlist metadata and ordered track snapshots."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.storage.database import initialize_database

_PROVIDER_ID = "yandex_music"
_PLAYLIST_PREFIX = "playlist:"


@dataclass(frozen=True, slots=True)
class PlaylistCacheSnapshot:
    metadata: dict[str, Any]
    tracks: list[dict[str, Any]]
    refreshed_at: str | None
    content_refreshed_at: str | None

    @property
    def count(self) -> int:
        return len(self.tracks)


def _collection_id(external_id: str) -> str:
    return f"{_PLAYLIST_PREFIX}{external_id}"


def _track_payload(track: ProviderTrack) -> dict[str, Any]:
    return {
        "provider_id": track.provider_id,
        "external_id": track.external_id,
        "title": track.title,
        "artists": list(track.artists),
        "album_external_id": track.album_external_id,
        "album_title": track.album_title,
        "duration_seconds": track.duration_seconds,
        "explicit": track.explicit,
        "availability": track.availability,
        "artwork_url": track.artwork_url,
    }


def _playlist_track_count(playlist: ProviderPlaylist) -> int:
    raw = playlist.raw_data
    for key in ("track_count", "trackCount"):
        value = raw.get(key)
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return len(playlist.track_external_ids)


def _playlist_uuid(playlist: ProviderPlaylist) -> str | None:
    """Return the provider playlist UUID without persisting unrelated raw payload."""
    raw = playlist.raw_data
    for key in ("playlist_uuid", "playlistUuid", "uuid"):
        value = raw.get(key)
        clean = str(value or "").strip()
        if clean:
            return clean
    return None


def _playlist_metadata(playlist: ProviderPlaylist) -> dict[str, Any]:
    metadata = {
        "providerId": playlist.provider_id,
        "externalId": playlist.external_id,
        "title": playlist.title,
        "ownerName": playlist.owner_name,
        "visibility": playlist.visibility,
        "trackCount": _playlist_track_count(playlist),
    }
    playlist_uuid = _playlist_uuid(playlist)
    if playlist_uuid:
        metadata["playlistUuid"] = playlist_uuid
    return metadata


def _unique_playlists(playlists: Iterable[ProviderPlaylist]) -> list[ProviderPlaylist]:
    result: list[ProviderPlaylist] = []
    seen: set[str] = set()
    for playlist in playlists:
        external_id = playlist.external_id.strip()
        if not external_id or external_id in seen:
            continue
        seen.add(external_id)
        result.append(playlist)
    return result


def _storage_item_id(external_id: str, occurrence: int) -> str:
    if occurrence == 0:
        return external_id
    return f"{external_id}::duplicate:{occurrence}"


class PlaylistCacheRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def list_metadata(self) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT metadata_json, external_id, title, owner_name, item_count,
                           refreshed_at, content_refreshed_at, source_position
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_type='playlist' AND active=1
                    ORDER BY source_position ASC, title COLLATE NOCASE ASC
                    """,
                    (_PROVIDER_ID,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to read playlist metadata cache: {exc}") from exc

        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                metadata = json.loads(row[0]) if row[0] else {}
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            metadata.update(
                {
                    "externalId": metadata.get("externalId") or str(row[1] or ""),
                    "title": metadata.get("title") or str(row[2] or ""),
                    "ownerName": metadata.get("ownerName") or row[3],
                    "trackCount": int(metadata.get("trackCount", row[4] or 0)),
                    "lastUpdated": str(row[5]) if row[5] else None,
                    "contentLastUpdated": str(row[6]) if row[6] else None,
                    "sourcePosition": int(row[7] or 0),
                }
            )
            result.append(metadata)
        return result

    def replace_index(self, playlists: Iterable[ProviderPlaylist]) -> dict[str, int]:
        playlist_list = _unique_playlists(playlists)
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        incoming_ids = {playlist.external_id for playlist in playlist_list}

        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                existing_rows = conn.execute(
                    """
                    SELECT external_id
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_type='playlist' AND active=1
                    """,
                    (_PROVIDER_ID,),
                ).fetchall()
                existing_ids = {str(row[0]) for row in existing_rows if row[0]}
                stale_ids = existing_ids - incoming_ids

                with conn:
                    for external_id in stale_ids:
                        collection_id = _collection_id(external_id)
                        conn.execute(
                            "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                            (_PROVIDER_ID, collection_id),
                        )
                        conn.execute(
                            "DELETE FROM provider_collection_snapshots WHERE provider_id=? AND collection_id=?",
                            (_PROVIDER_ID, collection_id),
                        )

                    for position, playlist in enumerate(playlist_list):
                        metadata = _playlist_metadata(playlist)
                        conn.execute(
                            """
                            INSERT INTO provider_collection_snapshots(
                                provider_id, collection_id, account_json, item_count, refreshed_at,
                                collection_type, external_id, title, owner_name, metadata_json,
                                source_position, active
                            ) VALUES (?, ?, '{}', ?, ?, 'playlist', ?, ?, ?, ?, ?, 1)
                            ON CONFLICT(provider_id, collection_id) DO UPDATE SET
                                item_count=excluded.item_count,
                                refreshed_at=excluded.refreshed_at,
                                collection_type='playlist',
                                external_id=excluded.external_id,
                                title=excluded.title,
                                owner_name=excluded.owner_name,
                                metadata_json=excluded.metadata_json,
                                source_position=excluded.source_position,
                                active=1
                            """,
                            (
                                _PROVIDER_ID,
                                _collection_id(playlist.external_id),
                                _playlist_track_count(playlist),
                                now,
                                playlist.external_id,
                                playlist.title,
                                playlist.owner_name,
                                json.dumps(metadata, ensure_ascii=False),
                                position,
                            ),
                        )
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to update playlist metadata cache: {exc}") from exc

        return {
            "added": len(incoming_ids - existing_ids),
            "removed": len(stale_ids),
            "unchanged": len(incoming_ids & existing_ids),
        }

    def load(self, external_id: str) -> PlaylistCacheSnapshot:
        clean_id = external_id.strip()
        collection_id = _collection_id(clean_id)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                meta = conn.execute(
                    """
                    SELECT metadata_json, title, owner_name, item_count, refreshed_at,
                           content_refreshed_at
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_id=? AND collection_type='playlist' AND active=1
                    """,
                    (_PROVIDER_ID, collection_id),
                ).fetchone()
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM provider_collection_items
                    WHERE provider_id=? AND collection_id=?
                    ORDER BY position ASC
                    """,
                    (_PROVIDER_ID, collection_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to read playlist cache: {exc}") from exc

        if meta is None:
            return PlaylistCacheSnapshot(
                metadata={"externalId": clean_id, "title": "", "trackCount": 0},
                tracks=[],
                refreshed_at=None,
                content_refreshed_at=None,
            )

        try:
            metadata = json.loads(meta[0]) if meta[0] else {}
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        metadata.update(
            {
                "externalId": metadata.get("externalId") or clean_id,
                "title": metadata.get("title") or str(meta[1] or ""),
                "ownerName": metadata.get("ownerName") or meta[2],
                "trackCount": int(metadata.get("trackCount", meta[3] or 0)),
                "lastUpdated": str(meta[4]) if meta[4] else None,
                "contentLastUpdated": str(meta[5]) if meta[5] else None,
            }
        )
        tracks = [json.loads(row[0]) for row in rows]
        return PlaylistCacheSnapshot(
            metadata=metadata,
            tracks=tracks,
            refreshed_at=str(meta[4]) if meta[4] else None,
            content_refreshed_at=str(meta[5]) if meta[5] else None,
        )

    def replace_playlist(
        self,
        playlist: ProviderPlaylist,
        tracks: Iterable[ProviderTrack],
    ) -> dict[str, int]:
        clean_id = playlist.external_id.strip()
        if not clean_id:
            raise StorageError("Cannot cache a playlist without an external id.")
        track_list = [track for track in tracks if track.external_id.strip()]
        collection_id = _collection_id(clean_id)
        metadata = _playlist_metadata(playlist)
        metadata["trackCount"] = len(track_list)
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        new_counter = Counter(track.external_id for track in track_list)

        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                before_rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM provider_collection_items
                    WHERE provider_id=? AND collection_id=?
                    """,
                    (_PROVIDER_ID, collection_id),
                ).fetchall()
                before_ids = []
                for row in before_rows:
                    try:
                        before_ids.append(str(json.loads(row[0]).get("external_id", "")))
                    except (TypeError, json.JSONDecodeError, AttributeError):
                        continue
                before_counter = Counter(value for value in before_ids if value)

                source_row = conn.execute(
                    """
                    SELECT source_position
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_id=?
                    """,
                    (_PROVIDER_ID, collection_id),
                ).fetchone()
                source_position = int(source_row[0]) if source_row else 0

                with conn:
                    conn.execute(
                        "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                        (_PROVIDER_ID, collection_id),
                    )
                    occurrences: Counter[str] = Counter()
                    rows_to_insert: list[tuple[str, str, str, int, str]] = []
                    for position, track in enumerate(track_list):
                        occurrence = occurrences[track.external_id]
                        occurrences[track.external_id] += 1
                        rows_to_insert.append(
                            (
                                _PROVIDER_ID,
                                collection_id,
                                _storage_item_id(track.external_id, occurrence),
                                position,
                                json.dumps(_track_payload(track), ensure_ascii=False),
                            )
                        )
                    if rows_to_insert:
                        conn.executemany(
                            """
                            INSERT INTO provider_collection_items(
                                provider_id, collection_id, external_id, position, payload_json
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            rows_to_insert,
                        )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at,
                            collection_type, external_id, title, owner_name, metadata_json,
                            source_position, active, content_refreshed_at
                        ) VALUES (?, ?, '{}', ?, ?, 'playlist', ?, ?, ?, ?, ?, 1, ?)
                        ON CONFLICT(provider_id, collection_id) DO UPDATE SET
                            item_count=excluded.item_count,
                            refreshed_at=excluded.refreshed_at,
                            collection_type='playlist',
                            external_id=excluded.external_id,
                            title=excluded.title,
                            owner_name=excluded.owner_name,
                            metadata_json=excluded.metadata_json,
                            active=1,
                            content_refreshed_at=excluded.content_refreshed_at
                        """,
                        (
                            _PROVIDER_ID,
                            collection_id,
                            len(track_list),
                            now,
                            clean_id,
                            playlist.title,
                            playlist.owner_name,
                            json.dumps(metadata, ensure_ascii=False),
                            source_position,
                            now,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to update playlist cache: {exc}") from exc

        unchanged = sum((before_counter & new_counter).values())
        added = sum((new_counter - before_counter).values())
        removed = sum((before_counter - new_counter).values())
        return {"added": added, "removed": removed, "unchanged": unchanged}

    def clear(self) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    rows = conn.execute(
                        """
                        SELECT collection_id
                        FROM provider_collection_snapshots
                        WHERE provider_id=? AND collection_type='playlist'
                        """,
                        (_PROVIDER_ID,),
                    ).fetchall()
                    collection_ids = [str(row[0]) for row in rows]
                    if collection_ids:
                        conn.executemany(
                            "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                            [(_PROVIDER_ID, collection_id) for collection_id in collection_ids],
                        )
                    conn.execute(
                        "DELETE FROM provider_collection_snapshots WHERE provider_id=? AND collection_type='playlist'",
                        (_PROVIDER_ID,),
                    )
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to clear playlist cache: {exc}") from exc
