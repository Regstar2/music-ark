"""SQLite repository for MusicArk local library roots and audio index."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.local_library.models import LocalAudioRecord, LocalLibraryRoot
from musicark.providers.models import LocalAudioFile, TrackSource


def normalize_local_path(path: str | Path) -> str:
    """Return the canonical local path key used for case-insensitive comparisons."""
    resolved = Path(path).expanduser().resolve(strict=False)
    text = str(resolved).replace("\\", "/").rstrip("/")
    return text.casefold()


def _is_overlapping(a: str, b: str) -> bool:
    return a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")


class LocalLibraryStorageRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_roots(self) -> list[LocalLibraryRoot]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, path, normalized_path, enabled, created_at, last_scanned_at
                    FROM local_library_roots
                    ORDER BY path COLLATE NOCASE
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list local library roots.") from exc
        return [LocalLibraryRoot(int(r[0]), r[1], r[2], bool(r[3]), r[4], r[5]) for r in rows]

    def add_root(self, path: Path) -> LocalLibraryRoot:
        resolved = path.expanduser().resolve(strict=False)
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"Local library root is not a directory: {path}")
        normalized = normalize_local_path(resolved)
        roots = self.list_roots()
        for root in roots:
            if root.normalized_path == normalized:
                raise ValueError("This folder is already in the local library.")
            if _is_overlapping(normalized, root.normalized_path):
                raise ValueError(
                    "Overlapping local library roots are not allowed; add either the parent or the child folder."
                )
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO local_library_roots(path, normalized_path) VALUES (?, ?)",
                        (str(resolved), normalized),
                    )
                    root_id = int(cursor.lastrowid)
                    row = conn.execute(
                        """
                        SELECT id, path, normalized_path, enabled, created_at, last_scanned_at
                        FROM local_library_roots WHERE id=?
                        """,
                        (root_id,),
                    ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to add local library root.") from exc
        assert row is not None
        return LocalLibraryRoot(int(row[0]), row[1], row[2], bool(row[3]), row[4], row[5])

    def remove_root(self, root_id: int) -> bool:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    paths = [
                        row[0]
                        for row in conn.execute(
                            "SELECT path FROM local_audio_files WHERE library_root_id=?",
                            (int(root_id),),
                        ).fetchall()
                    ]
                    conn.execute("DELETE FROM local_audio_files WHERE library_root_id=?", (int(root_id),))
                    if paths:
                        conn.executemany(
                            "DELETE FROM track_sources WHERE provider_id='local_library' AND external_id=?",
                            ((path,) for path in paths),
                        )
                    cursor = conn.execute("DELETE FROM local_library_roots WHERE id=?", (int(root_id),))
                    return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StorageError("Failed to remove local library root.") from exc

    def file_states(self, root_id: int) -> dict[str, dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, normalized_path, file_size, modified_ns, sha256
                    FROM local_audio_files
                    WHERE library_root_id=? AND availability='available'
                    """,
                    (int(root_id),),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load local file states.") from exc
        return {
            str(row[1]): {
                "id": int(row[0]),
                "file_size": int(row[2]),
                "modified_ns": int(row[3] or 0),
                "sha256": row[4] or "",
            }
            for row in rows
        }

    def apply_scan(
        self,
        root_id: int,
        *,
        upserts: Iterable[LocalAudioRecord],
        seen_normalized_paths: set[str],
        scanned_at: str,
        allow_removals: bool,
    ) -> int:
        rows = [self._record_tuple(item, scanned_at) for item in upserts]
        removed = 0
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute("CREATE TEMP TABLE IF NOT EXISTS local_scan_seen(path TEXT PRIMARY KEY)")
                    conn.execute("DELETE FROM local_scan_seen")
                    if seen_normalized_paths:
                        conn.executemany(
                            "INSERT OR IGNORE INTO local_scan_seen(path) VALUES (?)",
                            ((path,) for path in seen_normalized_paths),
                        )
                    if rows:
                        conn.executemany(
                            """
                            INSERT INTO local_audio_files(
                                library_root_id, path, normalized_path, file_name, extension,
                                sha256, file_size, modified_ns, duration_seconds, codec,
                                metadata_json, title, artists_json, album, album_artist,
                                track_number, disc_number, year, genre, bitrate, sample_rate,
                                availability, last_seen_at
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'available',?)
                            ON CONFLICT(normalized_path) DO UPDATE SET
                                library_root_id=excluded.library_root_id,
                                path=excluded.path,
                                file_name=excluded.file_name,
                                extension=excluded.extension,
                                sha256=excluded.sha256,
                                file_size=excluded.file_size,
                                modified_ns=excluded.modified_ns,
                                duration_seconds=excluded.duration_seconds,
                                codec=excluded.codec,
                                metadata_json=excluded.metadata_json,
                                title=excluded.title,
                                artists_json=excluded.artists_json,
                                album=excluded.album,
                                album_artist=excluded.album_artist,
                                track_number=excluded.track_number,
                                disc_number=excluded.disc_number,
                                year=excluded.year,
                                genre=excluded.genre,
                                bitrate=excluded.bitrate,
                                sample_rate=excluded.sample_rate,
                                availability='available',
                                last_seen_at=excluded.last_seen_at,
                                updated_at=datetime('now')
                            """,
                            rows,
                        )
                    conn.execute(
                        """
                        UPDATE local_audio_files
                        SET last_seen_at=?
                        WHERE library_root_id=?
                          AND normalized_path IN (SELECT path FROM local_scan_seen)
                        """,
                        (scanned_at, int(root_id)),
                    )
                    if allow_removals:
                        cursor = conn.execute(
                            """
                            DELETE FROM local_audio_files
                            WHERE library_root_id=?
                              AND normalized_path NOT IN (SELECT path FROM local_scan_seen)
                            """,
                            (int(root_id),),
                        )
                        removed = max(0, int(cursor.rowcount))
                    conn.execute(
                        "UPDATE local_library_roots SET last_scanned_at=? WHERE id=?",
                        (scanned_at, int(root_id)),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist local library scan.") from exc
        return removed

    @staticmethod
    def _record_tuple(item: LocalAudioRecord, scanned_at: str) -> tuple[Any, ...]:
        metadata = item.metadata
        payload = {
            "title": metadata.title,
            "artists": list(metadata.artists),
            "album": metadata.album,
            "album_artist": metadata.album_artist,
            "track_number": metadata.track_number,
            "disc_number": metadata.disc_number,
            "year": metadata.year,
            "genre": metadata.genre,
            "duration_seconds": metadata.duration_seconds,
            "codec": metadata.codec,
            "bitrate": metadata.bitrate,
            "sample_rate": metadata.sample_rate,
        }
        return (
            item.library_root_id,
            item.path,
            item.normalized_path,
            item.file_name,
            item.extension,
            item.sha256,
            item.file_size,
            item.modified_ns,
            metadata.duration_seconds,
            metadata.codec,
            json.dumps(payload, ensure_ascii=False),
            metadata.title,
            json.dumps(list(metadata.artists), ensure_ascii=False),
            metadata.album,
            metadata.album_artist,
            metadata.track_number,
            metadata.disc_number,
            metadata.year,
            metadata.genre,
            metadata.bitrate,
            metadata.sample_rate,
            scanned_at,
        )

    def list_tracks(
        self,
        *,
        limit: int,
        offset: int,
        search: str = "",
        sort: str = "artist",
        root_id: int | None = None,
        root_ids: Iterable[int] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List tracks, optionally limiting the query to one or more roots.

        ``root_ids`` deliberately distinguishes ``None`` (all roots) from an
        empty iterable (no roots).  The root predicate is applied before COUNT,
        ORDER BY, LIMIT and OFFSET so pagination always reflects the selected
        library subset.
        """
        if root_id is not None and root_ids is not None:
            raise ValueError("root_id and root_ids cannot be supplied together.")

        order_by = {
            "artist": "COALESCE(artists_json, '[]') COLLATE NOCASE, title COLLATE NOCASE",
            "title": "title COLLATE NOCASE, path COLLATE NOCASE",
            "album": "COALESCE(album, '') COLLATE NOCASE, title COLLATE NOCASE",
            "duration": "COALESCE(duration_seconds, 0), title COLLATE NOCASE",
            "path": "path COLLATE NOCASE",
            "original": "id",
        }.get(sort, "COALESCE(artists_json, '[]') COLLATE NOCASE, title COLLATE NOCASE")
        where = ["availability='available'", "library_root_id IS NOT NULL"]
        params: list[Any] = []

        if root_ids is not None:
            normalized_root_ids = list(dict.fromkeys(int(value) for value in root_ids))
            if normalized_root_ids:
                placeholders = ",".join("?" for _ in normalized_root_ids)
                where.append(f"library_root_id IN ({placeholders})")
                params.extend(normalized_root_ids)
            else:
                where.append("1=0")
        elif root_id is not None:
            where.append("library_root_id=?")
            params.append(int(root_id))

        query = search.strip()
        if query:
            where.append(
                "(title LIKE ? COLLATE NOCASE OR artists_json LIKE ? COLLATE NOCASE OR "
                "COALESCE(album,'') LIKE ? COLLATE NOCASE OR file_name LIKE ? COLLATE NOCASE)"
            )
            needle = f"%{query}%"
            params.extend([needle, needle, needle, needle])
        where_sql = " AND ".join(where)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM local_audio_files WHERE {where_sql}",
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    f"""
                    SELECT id, library_root_id, path, file_name, extension, file_size, modified_ns,
                           title, artists_json, album, album_artist, duration_seconds, codec,
                           bitrate, sample_rate, track_number, disc_number, year, genre
                    FROM local_audio_files
                    WHERE {where_sql}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, int(limit), int(offset)],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to query local tracks.") from exc
        return [self._row_to_track(row) for row in rows], total

    def get_track(self, track_id: int) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT id, library_root_id, path, file_name, extension, file_size, modified_ns,
                           title, artists_json, album, album_artist, duration_seconds, codec,
                           bitrate, sample_rate, track_number, disc_number, year, genre
                    FROM local_audio_files WHERE id=? AND availability='available'
                    """,
                    (int(track_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load local track.") from exc
        return self._row_to_track(row) if row else None

    @staticmethod
    def _row_to_track(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            artists = json.loads(row[8] or "[]")
        except json.JSONDecodeError:
            artists = []
        return {
            "id": int(row[0]),
            "rootId": int(row[1]) if row[1] is not None else None,
            "path": row[2],
            "fileName": row[3],
            "extension": row[4],
            "fileSize": int(row[5]),
            "modifiedNs": int(row[6] or 0),
            "title": row[7] or Path(row[2]).stem,
            "artists": artists if isinstance(artists, list) else [],
            "album": row[9],
            "albumArtist": row[10],
            "durationSeconds": row[11],
            "codec": row[12],
            "bitrate": row[13],
            "sampleRate": row[14],
            "trackNumber": row[15],
            "discNumber": row[16],
            "year": row[17],
            "genre": row[18],
        }

    # ---- Legacy compatibility used by pre-v0.4 tests/modules. ----
    def upsert_local_audio_file(self, audio_file: LocalAudioFile) -> None:
        metadata_json = json.dumps(audio_file.metadata_json, ensure_ascii=False)
        path = str(Path(audio_file.path).resolve(strict=False))
        normalized = normalize_local_path(path)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            path, normalized_path, file_name, extension, sha256, file_size,
                            duration_seconds, codec, metadata_json, availability
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available')
                        ON CONFLICT(normalized_path) DO UPDATE SET
                            path=excluded.path, sha256=excluded.sha256,
                            file_size=excluded.file_size, duration_seconds=excluded.duration_seconds,
                            codec=excluded.codec, metadata_json=excluded.metadata_json,
                            availability='available', updated_at=datetime('now')
                        """,
                        (
                            path,
                            normalized,
                            Path(path).name,
                            Path(path).suffix.lower(),
                            audio_file.sha256,
                            audio_file.file_size,
                            audio_file.duration_seconds,
                            audio_file.codec,
                            metadata_json,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist local audio file.") from exc

    def upsert_local_audio_file_and_return_id(self, audio_file: LocalAudioFile) -> int:
        self.upsert_local_audio_file(audio_file)
        normalized = normalize_local_path(audio_file.path)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT id FROM local_audio_files WHERE normalized_path=?",
                    (normalized,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to fetch local audio file id.") from exc
        if row is None:
            raise StorageError("Local audio file id was not found after upsert.")
        return int(row[0])

    def upsert_track_source(self, track_source: TrackSource) -> None:
        raw_data_json = json.dumps(track_source.raw_data, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO track_sources(track_id, source_type, provider_id, external_id, url, availability, raw_data_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            track_id=excluded.track_id, source_type=excluded.source_type,
                            url=excluded.url, availability=excluded.availability,
                            raw_data_json=excluded.raw_data_json, last_seen_at=datetime('now')
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
                    "SELECT path, sha256, file_size, duration_seconds, codec FROM local_audio_files ORDER BY path"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list local audio files.") from exc
        return [
            {
                "path": r[0],
                "sha256": r[1],
                "file_size": r[2],
                "duration_seconds": r[3],
                "codec": r[4],
            }
            for r in rows
        ]

    def fetch_local_audio_file_row_by_id(self, file_id: int) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT id, path, sha256, file_size, duration_seconds, codec, metadata_json FROM local_audio_files WHERE id=?",
                    (int(file_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load local audio file row.") from exc
        if row is None:
            return None
        return {
            "id": row[0],
            "path": row[1],
            "sha256": row[2],
            "file_size": row[3],
            "duration_seconds": row[4],
            "codec": row[5],
            "metadata_json": json.loads(row[6] or "{}"),
        }

    def local_stats(self) -> dict:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM local_audio_files WHERE availability='available'"
                    ).fetchone()[0]
                )
                by_codec_rows = conn.execute(
                    "SELECT codec, COUNT(*) FROM local_audio_files WHERE availability='available' GROUP BY codec ORDER BY codec"
                ).fetchall()
                roots = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM local_library_roots WHERE enabled=1"
                    ).fetchone()[0]
                )
        except sqlite3.Error as exc:
            raise StorageError("Failed to compute local audio stats.") from exc
        return {
            "total_files": total,
            "enabled_roots": roots,
            "by_codec": {row[0]: row[1] for row in by_codec_rows},
        }
