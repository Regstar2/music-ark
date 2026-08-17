"""SQLite cache for Yandex liked albums and lazily loaded album tracks."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.providers.models import ProviderTrack
from musicark.storage.database import initialize_database

_PROVIDER_ID = "yandex_music"
_INDEX_ID = "liked_albums"
_DETAIL_PREFIX = "album:"


@dataclass(frozen=True, slots=True)
class AlbumCacheSnapshot:
    metadata: dict[str, Any]
    tracks: list[dict[str, Any]]
    refreshed_at: str | None
    content_refreshed_at: str | None

    @property
    def count(self) -> int:
        return len(self.tracks)


def _detail_id(external_id: str) -> str:
    return f"{_DETAIL_PREFIX}{external_id}"


def _album(raw: dict[str, Any]) -> dict[str, Any]:
    artists = raw.get("artists") if isinstance(raw.get("artists"), list) else []
    return {
        "providerId": _PROVIDER_ID,
        "externalId": str(raw.get("externalId") or raw.get("external_id") or "").strip(),
        "title": str(raw.get("title") or "").strip(),
        "artists": [str(value).strip() for value in artists if str(value).strip()],
        "artworkUrl": str(raw.get("artworkUrl") or raw.get("artwork_url") or "").strip() or None,
        "trackCount": int(raw.get("trackCount") or raw.get("track_count") or 0),
        "year": raw.get("year"),
        "releaseDate": raw.get("releaseDate") or raw.get("release_date"),
        "availability": raw.get("availability"),
        "likedAt": raw.get("likedAt") or raw.get("liked_at"),
    }


def _track(track: ProviderTrack) -> dict[str, Any]:
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


class AlbumCacheRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def list_metadata(self) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT payload_json FROM provider_collection_items WHERE provider_id=? AND collection_id=? ORDER BY position",
                    (_PROVIDER_ID, _INDEX_ID),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to read liked-album cache: {exc}") from exc
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                value = json.loads(row[0])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                result.append(_album(value))
        return result

    def index_refreshed_at(self) -> str | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT refreshed_at FROM provider_collection_snapshots WHERE provider_id=? AND collection_id=?",
                    (_PROVIDER_ID, _INDEX_ID),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to read liked-album timestamp: {exc}") from exc
        return str(row[0]) if row and row[0] else None

    def replace_index(self, albums: Iterable[dict[str, Any]]) -> dict[str, int]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in albums:
            item = _album(raw)
            external_id = item["externalId"]
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)
            normalized.append(item)
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                before = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT external_id FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                        (_PROVIDER_ID, _INDEX_ID),
                    ).fetchall()
                }
                removed = before - seen
                with conn:
                    conn.execute(
                        "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                        (_PROVIDER_ID, _INDEX_ID),
                    )
                    conn.executemany(
                        "INSERT INTO provider_collection_items(provider_id, collection_id, external_id, position, payload_json) VALUES (?, ?, ?, ?, ?)",
                        [
                            (_PROVIDER_ID, _INDEX_ID, item["externalId"], position, json.dumps(item, ensure_ascii=False))
                            for position, item in enumerate(normalized)
                        ],
                    )
                    conn.execute(
                        """INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at,
                            collection_type, title, metadata_json, source_position, active
                        ) VALUES (?, ?, '{}', ?, ?, 'liked_albums', 'Liked albums', '{}', 0, 1)
                        ON CONFLICT(provider_id, collection_id) DO UPDATE SET
                            item_count=excluded.item_count, refreshed_at=excluded.refreshed_at,
                            collection_type='liked_albums', active=1""",
                        (_PROVIDER_ID, _INDEX_ID, len(normalized), now),
                    )
                    for external_id in removed:
                        collection_id = _detail_id(external_id)
                        conn.execute("DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?", (_PROVIDER_ID, collection_id))
                        conn.execute("DELETE FROM provider_collection_snapshots WHERE provider_id=? AND collection_id=?", (_PROVIDER_ID, collection_id))
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to update liked-album cache: {exc}") from exc
        return {"added": len(seen - before), "removed": len(before - seen), "unchanged": len(before & seen)}

    def load(self, external_id: str) -> AlbumCacheSnapshot:
        clean_id = external_id.strip()
        collection_id = _detail_id(clean_id)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                meta = conn.execute(
                    "SELECT metadata_json, refreshed_at, content_refreshed_at FROM provider_collection_snapshots WHERE provider_id=? AND collection_id=? AND active=1",
                    (_PROVIDER_ID, collection_id),
                ).fetchone()
                rows = conn.execute(
                    "SELECT payload_json FROM provider_collection_items WHERE provider_id=? AND collection_id=? ORDER BY position",
                    (_PROVIDER_ID, collection_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to read album cache: {exc}") from exc
        if meta is None:
            metadata = next((item for item in self.list_metadata() if item["externalId"] == clean_id), {"externalId": clean_id, "title": ""})
            return AlbumCacheSnapshot(_album(metadata), [], None, None)
        try:
            metadata = json.loads(meta[0]) if meta[0] else {}
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        return AlbumCacheSnapshot(
            _album(metadata),
            [json.loads(row[0]) for row in rows],
            str(meta[1]) if meta[1] else None,
            str(meta[2]) if meta[2] else None,
        )

    def replace_album(self, album: dict[str, Any], tracks: Iterable[ProviderTrack]) -> dict[str, int]:
        metadata = _album(album)
        external_id = metadata["externalId"]
        if not external_id:
            raise StorageError("Cannot cache an album without an external id.")
        track_list = [track for track in tracks if track.external_id.strip()]
        metadata["trackCount"] = len(track_list)
        collection_id = _detail_id(external_id)
        new_ids = {track.external_id for track in track_list}
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                before = {str(row[0]) for row in conn.execute("SELECT external_id FROM provider_collection_items WHERE provider_id=? AND collection_id=?", (_PROVIDER_ID, collection_id)).fetchall()}
                with conn:
                    conn.execute("DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?", (_PROVIDER_ID, collection_id))
                    conn.executemany(
                        "INSERT INTO provider_collection_items(provider_id, collection_id, external_id, position, payload_json) VALUES (?, ?, ?, ?, ?)",
                        [(_PROVIDER_ID, collection_id, track.external_id, position, json.dumps(_track(track), ensure_ascii=False)) for position, track in enumerate(track_list)],
                    )
                    conn.execute(
                        """INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at,
                            collection_type, external_id, title, metadata_json,
                            source_position, active, content_refreshed_at
                        ) VALUES (?, ?, '{}', ?, ?, 'album', ?, ?, ?, 0, 1, ?)
                        ON CONFLICT(provider_id, collection_id) DO UPDATE SET
                            item_count=excluded.item_count, refreshed_at=excluded.refreshed_at,
                            collection_type='album', external_id=excluded.external_id,
                            title=excluded.title, metadata_json=excluded.metadata_json,
                            active=1, content_refreshed_at=excluded.content_refreshed_at""",
                        (_PROVIDER_ID, collection_id, len(track_list), now, external_id, metadata["title"], json.dumps(metadata, ensure_ascii=False), now),
                    )
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to update album cache: {exc}") from exc
        return {"added": len(new_ids - before), "removed": len(before - new_ids), "unchanged": len(before & new_ids)}

    def clear(self) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute("DELETE FROM provider_collection_items WHERE provider_id=? AND (collection_id=? OR collection_id LIKE ?)", (_PROVIDER_ID, _INDEX_ID, f"{_DETAIL_PREFIX}%"))
                    conn.execute("DELETE FROM provider_collection_snapshots WHERE provider_id=? AND (collection_id=? OR collection_id LIKE ?)", (_PROVIDER_ID, _INDEX_ID, f"{_DETAIL_PREFIX}%"))
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to clear liked-album cache: {exc}") from exc
