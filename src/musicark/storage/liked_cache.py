"""SQLite snapshot cache for provider liked-track collections."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.providers.models import ProviderTrack
from musicark.storage.database import initialize_database


_PROVIDER_ID = "yandex_music"
_COLLECTION_ID = "liked"


@dataclass(frozen=True, slots=True)
class LikedCacheSnapshot:
    account: dict[str, Any]
    tracks: list[dict[str, Any]]
    refreshed_at: str | None

    @property
    def count(self) -> int:
        return len(self.tracks)


class LikedCacheRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def load(self) -> LikedCacheSnapshot:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                meta = conn.execute(
                    """
                    SELECT account_json, refreshed_at
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_id=?
                    """,
                    (_PROVIDER_ID, _COLLECTION_ID),
                ).fetchone()
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM provider_collection_items
                    WHERE provider_id=? AND collection_id=?
                    ORDER BY position ASC
                    """,
                    (_PROVIDER_ID, _COLLECTION_ID),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read the liked-tracks cache.") from exc

        account = json.loads(meta[0]) if meta else {}
        refreshed_at = str(meta[1]) if meta else None
        tracks = [json.loads(row[0]) for row in rows]
        return LikedCacheSnapshot(account=account, tracks=tracks, refreshed_at=refreshed_at)

    def replace(
        self,
        account: dict[str, Any],
        tracks: Iterable[ProviderTrack],
    ) -> dict[str, int]:
        track_list = list(tracks)
        refreshed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        new_ids = {track.external_id for track in track_list}

        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                before_rows = conn.execute(
                    """
                    SELECT external_id
                    FROM provider_collection_items
                    WHERE provider_id=? AND collection_id=?
                    """,
                    (_PROVIDER_ID, _COLLECTION_ID),
                ).fetchall()
                before_ids = {str(row[0]) for row in before_rows}

                with conn:
                    conn.execute(
                        """
                        DELETE FROM provider_collection_items
                        WHERE provider_id=? AND collection_id=?
                        """,
                        (_PROVIDER_ID, _COLLECTION_ID),
                    )
                    for position, track in enumerate(track_list):
                        conn.execute(
                            """
                            INSERT INTO provider_collection_items(
                                provider_id, collection_id, external_id, position, payload_json
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                _PROVIDER_ID,
                                _COLLECTION_ID,
                                track.external_id,
                                position,
                                json.dumps(asdict(track), ensure_ascii=False),
                            ),
                        )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(provider_id, collection_id) DO UPDATE SET
                            account_json=excluded.account_json,
                            item_count=excluded.item_count,
                            refreshed_at=excluded.refreshed_at
                        """,
                        (
                            _PROVIDER_ID,
                            _COLLECTION_ID,
                            json.dumps(account, ensure_ascii=False),
                            len(track_list),
                            refreshed_at,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to update the liked-tracks cache.") from exc

        return {
            "added": len(new_ids - before_ids),
            "removed": len(before_ids - new_ids),
            "unchanged": len(before_ids & new_ids),
        }

    def clear(self) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id=?",
                        (_PROVIDER_ID, _COLLECTION_ID),
                    )
                    conn.execute(
                        "DELETE FROM provider_collection_snapshots WHERE provider_id=? AND collection_id=?",
                        (_PROVIDER_ID, _COLLECTION_ID),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to clear the liked-tracks cache.") from exc
