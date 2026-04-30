"""Storage repository for local library scan records."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError
from musicark.providers.models import LocalAudioFile, TrackSource


class LocalLibraryStorageRepository:
    """Persists local audio files and local track sources."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def upsert_local_audio_file(self, audio_file: LocalAudioFile) -> None:
        metadata_json = json.dumps(audio_file.metadata_json, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            path, sha256, file_size, duration_seconds, codec, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            sha256=excluded.sha256,
                            file_size=excluded.file_size,
                            duration_seconds=excluded.duration_seconds,
                            codec=excluded.codec,
                            metadata_json=excluded.metadata_json,
                            updated_at=datetime('now')
                        """,
                        (
                            audio_file.path,
                            audio_file.sha256,
                            audio_file.file_size,
                            audio_file.duration_seconds,
                            audio_file.codec,
                            metadata_json,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist local audio file.") from exc

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
            raise StorageError("Failed to persist local track source.") from exc

    def list_local_audio_files(self) -> list[dict]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT path, sha256, file_size, duration_seconds, codec
                    FROM local_audio_files
                    ORDER BY path
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list local audio files.") from exc
        return [
            {
                "path": row[0],
                "sha256": row[1],
                "file_size": row[2],
                "duration_seconds": row[3],
                "codec": row[4],
            }
            for row in rows
        ]

    def local_stats(self) -> dict:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM local_audio_files").fetchone()[0]
                by_codec_rows = conn.execute(
                    "SELECT codec, COUNT(*) FROM local_audio_files GROUP BY codec ORDER BY codec"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to compute local audio stats.") from exc

        return {
            "total_files": total,
            "by_codec": {row[0]: row[1] for row in by_codec_rows},
        }
