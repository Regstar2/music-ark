"""Storage access layer for matching-engine and canonical library."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.matching.models import MatchConflict, MatchMethod, Track, TrackLink


class MatchingStorageRepository:
    """Reads candidates and persists canonical tracks/links/conflicts."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_provider_track_candidates(self) -> list[dict]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT pt.provider_id, pt.external_id, pt.payload_json, ts.id
                    FROM provider_tracks pt
                    LEFT JOIN track_sources ts
                      ON ts.provider_id = pt.provider_id AND ts.external_id = pt.external_id
                    ORDER BY pt.id
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read provider track candidates.") from exc
        candidates = []
        for provider_id, external_id, payload_json, source_row_id in rows:
            payload = json.loads(payload_json)
            candidates.append(
                {
                    "provider_id": provider_id,
                    "external_id": external_id,
                    "payload": payload,
                    "source_row_id": source_row_id,
                }
            )
        return candidates

    def list_track_links_for_provider(self, provider_id: str) -> list[dict[str, Any]]:
        """Expose track_links keyed by catalogue id for sync upload heuristics (v0.11)."""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT source_external_id, local_file_id, track_id
                    FROM track_links
                    WHERE source_provider_id=?
                    ORDER BY source_external_id
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list track links for provider.") from exc
        return [
            {"source_external_id": row[0], "local_file_id": int(row[1]), "track_id": int(row[2])}
            for row in rows
        ]

    def list_local_audio_files(self) -> list[dict]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, path, sha256, file_size, duration_seconds, codec, metadata_json
                    FROM local_audio_files
                    ORDER BY id
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read local audio files for matching.") from exc
        result = []
        for row in rows:
            metadata_json = json.loads(row[6] or "{}")
            result.append(
                {
                    "id": row[0],
                    "path": row[1],
                    "sha256": row[2],
                    "file_size": row[3],
                    "duration_seconds": row[4],
                    "codec": row[5],
                    "metadata_json": metadata_json,
                }
            )
        return result

    def upsert_track(self, track: Track) -> int:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    row = conn.execute(
                        """
                        SELECT id FROM tracks
                        WHERE normalized_title=? AND normalized_artists_json=?
                              AND COALESCE(album,'')=COALESCE(?, '')
                        """,
                        (
                            track.normalized_title,
                            json.dumps(track.normalized_artists, ensure_ascii=False),
                            track.album,
                        ),
                    ).fetchone()
                    if row:
                        track_id = int(row[0])
                        conn.execute(
                            """
                            UPDATE tracks
                            SET title=?, artists_json=?, album=?, duration_seconds=?, updated_at=datetime('now')
                            WHERE id=?
                            """,
                            (
                                track.title,
                                json.dumps(track.artists, ensure_ascii=False),
                                track.album,
                                track.duration_seconds,
                                track_id,
                            ),
                        )
                        return track_id

                    cursor = conn.execute(
                        """
                        INSERT INTO tracks(
                            title, artists_json, album, duration_seconds, normalized_title, normalized_artists_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            track.title,
                            json.dumps(track.artists, ensure_ascii=False),
                            track.album,
                            track.duration_seconds,
                            track.normalized_title,
                            json.dumps(track.normalized_artists, ensure_ascii=False),
                        ),
                    )
                    return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise StorageError("Failed to upsert canonical track.") from exc

    def upsert_track_link(self, link: TrackLink) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id, local_file_id,
                            confidence, match_method, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_provider_id, source_external_id, local_file_id)
                        DO UPDATE SET
                            track_id=excluded.track_id,
                            confidence=excluded.confidence,
                            match_method=excluded.match_method,
                            metadata_json=excluded.metadata_json,
                            updated_at=datetime('now')
                        """,
                        (
                            link.track_id,
                            link.source_provider_id,
                            link.source_external_id,
                            link.local_file_id,
                            link.confidence,
                            link.match_method.value,
                            json.dumps(link.metadata_json, ensure_ascii=False),
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to upsert track link.") from exc

    def insert_conflict(self, conflict: MatchConflict) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO match_conflicts(
                            source_provider_id, source_external_id, local_file_id, confidence, reason, status
                        ) VALUES (?, ?, ?, ?, ?, 'open')
                        """,
                        (
                            conflict.source_provider_id,
                            conflict.source_external_id,
                            conflict.local_file_id,
                            conflict.confidence,
                            conflict.reason,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist matching conflict.") from exc

    def list_open_conflicts(self) -> list[dict]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, source_provider_id, source_external_id, local_file_id, confidence, reason, status
                    FROM match_conflicts
                    WHERE status='open'
                    ORDER BY confidence DESC
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list open conflicts.") from exc
        return [
            {
                "id": row[0],
                "source_provider_id": row[1],
                "source_external_id": row[2],
                "local_file_id": row[3],
                "confidence": row[4],
                "reason": row[5],
                "status": row[6],
            }
            for row in rows
        ]

    def accept_conflict(self, conflict_id: int, track_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    row = conn.execute(
                        """
                        SELECT source_provider_id, source_external_id, local_file_id, confidence
                        FROM match_conflicts
                        WHERE id=? AND status='open'
                        """,
                        (conflict_id,),
                    ).fetchone()
                    if row is None:
                        raise StorageError(f"Open conflict '{conflict_id}' not found.")
                    conn.execute(
                        """
                        UPDATE match_conflicts SET status='accepted' WHERE id=?
                        """,
                        (conflict_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id, local_file_id,
                            confidence, match_method, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_provider_id, source_external_id, local_file_id)
                        DO UPDATE SET
                            track_id=excluded.track_id,
                            confidence=excluded.confidence,
                            match_method=excluded.match_method,
                            metadata_json=excluded.metadata_json,
                            updated_at=datetime('now')
                        """,
                        (
                            track_id,
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            MatchMethod.MANUAL.value,
                            "{}",
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to accept conflict.") from exc
