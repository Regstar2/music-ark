"""Bridge active Yandex collection cache into unique provider-track identities."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError


class MatchingInputRepository:
    """Materialize unique cached collection members into legacy provider_tracks.

    v0.3/v0.4 cache membership lives in provider_collection_items, while legacy
    matching/canonical code already uses provider_tracks as the provider identity
    table. This adapter keeps one row per (provider_id, external_id) and therefore
    prevents Liked + playlist membership from creating duplicate matching work.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def sync_provider_tracks(self, provider_id: str) -> int:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT collection_id, external_id, payload_json
                    FROM provider_collection_items
                    WHERE provider_id=?
                    ORDER BY CASE WHEN collection_id='liked' THEN 0 ELSE 1 END,
                             collection_id, position
                    """,
                    (provider_id,),
                ).fetchall()
                # Empty collection cache can mean legacy tests/data. Keep existing
                # provider_tracks in that case instead of destroying compatibility.
                if not rows:
                    return int(
                        conn.execute(
                            "SELECT COUNT(*) FROM provider_tracks WHERE provider_id=?",
                            (provider_id,),
                        ).fetchone()[0]
                    )

                unique: dict[str, str] = {}
                for _collection_id, external_id, payload_json in rows:
                    key = str(external_id).strip()
                    if key and key not in unique:
                        unique[key] = str(payload_json)

                with conn:
                    conn.executemany(
                        """
                        INSERT INTO provider_tracks(provider_id, external_id, payload_json)
                        VALUES (?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            payload_json=excluded.payload_json,
                            updated_at=datetime('now')
                        """,
                        ((provider_id, external_id, payload) for external_id, payload in unique.items()),
                    )
                    conn.execute(
                        "CREATE TEMP TABLE IF NOT EXISTS matching_active_provider_ids(external_id TEXT PRIMARY KEY)"
                    )
                    conn.execute("DELETE FROM matching_active_provider_ids")
                    conn.executemany(
                        "INSERT INTO matching_active_provider_ids(external_id) VALUES (?)",
                        ((external_id,) for external_id in unique),
                    )
                    # Provider identities removed from every cached collection are no
                    # longer part of the current matching dataset. Remove only local
                    # analytical/link rows; canonical tracks and Yandex cache remain.
                    conn.execute(
                        """
                        DELETE FROM track_links
                        WHERE source_provider_id=?
                          AND source_external_id NOT IN (
                            SELECT external_id FROM matching_active_provider_ids
                          )
                        """,
                        (provider_id,),
                    )
                    conn.execute(
                        """
                        DELETE FROM match_conflicts
                        WHERE source_provider_id=?
                          AND source_external_id NOT IN (
                            SELECT external_id FROM matching_active_provider_ids
                          )
                        """,
                        (provider_id,),
                    )
                    conn.execute(
                        """
                        DELETE FROM matching_results
                        WHERE provider_id=?
                          AND external_id NOT IN (
                            SELECT external_id FROM matching_active_provider_ids
                          )
                        """,
                        (provider_id,),
                    )
                    conn.execute(
                        """
                        DELETE FROM provider_tracks
                        WHERE provider_id=?
                          AND external_id NOT IN (
                            SELECT external_id FROM matching_active_provider_ids
                          )
                        """,
                        (provider_id,),
                    )
                return len(unique)
        except sqlite3.Error as exc:
            raise StorageError("Failed to materialize provider identities for matching.") from exc
