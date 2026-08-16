"""Bounded SQL-backed candidate generation for MusicArk v0.5/v0.8."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.storage.matching_storage import MatchingStorageRepository
from .normalize import artists_key, normalize_text
from .policy import CANDIDATE_LIMIT


_ACTIVE_ROOT_CLAUSE = """
    AND (
        NOT EXISTS (SELECT 1 FROM local_library_roots WHERE enabled=1)
        OR library_root_id IN (SELECT id FROM local_library_roots WHERE enabled=1)
    )
"""


class CandidateGenerator:
    """Generate plausible candidates only from the configured Local Library."""

    def __init__(
        self,
        repository: MatchingStorageRepository,
        *,
        database_path: Path,
        limit: int = CANDIDATE_LIMIT,
    ) -> None:
        self._repository = repository
        self._database_path = database_path
        self._limit = max(1, int(limit))
        self.comparison_count = 0

    def generate(
        self,
        provider: dict[str, Any],
        *,
        excluded_local_ids: set[int] | None = None,
    ) -> list[dict[str, Any]]:
        payload = provider["payload"]
        title = normalize_text(payload.get("title"))
        artists = artists_key(payload.get("artists") or ())
        duration = payload.get("duration_seconds")
        excluded = excluded_local_ids or set()

        found: dict[int, dict[str, Any]] = {}
        for candidate in self._exact_id_candidates(provider):
            file_id = int(candidate["id"])
            if file_id not in excluded:
                found[file_id] = candidate

        remaining = max(0, self._limit - len(found))
        if remaining:
            for candidate in self._metadata_candidates(
                normalized_title=title,
                normalized_artists=artists,
                duration_seconds=float(duration) if duration is not None else None,
                limit=remaining,
                excluded_local_ids=excluded | set(found),
            ):
                found[int(candidate["id"])] = candidate
                if len(found) >= self._limit:
                    break
        candidates = list(found.values())[: self._limit]
        self.comparison_count += len(candidates)
        return candidates

    def _metadata_candidates(
        self,
        *,
        normalized_title: str,
        normalized_artists: str,
        duration_seconds: float | None,
        limit: int,
        excluded_local_ids: set[int],
    ) -> list[dict[str, Any]]:
        if not normalized_title and not normalized_artists:
            return []
        page_limit = max(1, min(int(limit), 100))
        found: dict[int, tuple[Any, ...]] = {}

        def add_rows(conn: sqlite3.Connection, sql: str, params: list[Any]) -> None:
            remaining = page_limit - len(found)
            if remaining <= 0:
                return
            for row in conn.execute(sql, [*params, remaining]).fetchall():
                file_id = int(row[0])
                if file_id not in excluded_local_ids:
                    found.setdefault(file_id, row)
                    if len(found) >= page_limit:
                        break

        columns = """
            id, path, title, artists_json, album, duration_seconds, codec,
            metadata_json, normalized_title, normalized_artists_text,
            duration_bucket, modified_ns, updated_at
        """
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                if normalized_title:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_title=?
                        {_ACTIVE_ROOT_CLAUSE}
                        ORDER BY CASE WHEN normalized_artists_text=? THEN 0 ELSE 1 END,
                                 COALESCE(duration_seconds, 0)
                        LIMIT ?
                        """,
                        [normalized_title, normalized_artists],
                    )
                if normalized_title and len(found) < page_limit:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_title LIKE ?
                        {_ACTIVE_ROOT_CLAUSE}
                        ORDER BY CASE WHEN normalized_artists_text=? THEN 0 ELSE 1 END,
                                 LENGTH(normalized_title)
                        LIMIT ?
                        """,
                        [f"{normalized_title} %", normalized_artists],
                    )
                if normalized_artists and duration_seconds is not None and len(found) < page_limit:
                    bucket = int(round(float(duration_seconds))) // 5
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available'
                          AND normalized_artists_text=?
                          AND duration_bucket BETWEEN ? AND ?
                          {_ACTIVE_ROOT_CLAUSE}
                        ORDER BY ABS(COALESCE(duration_seconds, 0) - ?)
                        LIMIT ?
                        """,
                        [normalized_artists, bucket - 2, bucket + 2, float(duration_seconds)],
                    )
                if normalized_artists and len(found) < page_limit:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_artists_text=?
                        {_ACTIVE_ROOT_CLAUSE}
                        ORDER BY CASE WHEN normalized_title=? THEN 0 ELSE 1 END, normalized_title
                        LIMIT ?
                        """,
                        [normalized_artists, normalized_title],
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to generate Local Library matching candidates.") from exc
        return [self._row(row) for row in found.values()]

    def _exact_id_candidates(self, provider: dict[str, Any]) -> list[dict[str, Any]]:
        if provider.get("provider_id") != "yandex_music":
            return []
        external_id = str(provider.get("external_id") or "").strip()
        if not external_id:
            return []
        underscore = f"yandex_{external_id}"
        hyphen = f"yandex-{external_id}"
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    f"""
                    SELECT id, path, title, artists_json, album, duration_seconds, codec,
                           metadata_json, normalized_title, normalized_artists_text,
                           duration_bucket, modified_ns, updated_at
                    FROM local_audio_files
                    WHERE (
                        (NOT EXISTS (SELECT 1 FROM local_library_roots WHERE enabled=1)
                         AND availability IN ('available', 'legacy'))
                        OR
                        (availability='available'
                         AND library_root_id IN (SELECT id FROM local_library_roots WHERE enabled=1))
                    )
                      AND (
                        file_name=? COLLATE NOCASE OR file_name LIKE ? COLLATE NOCASE
                        OR file_name=? COLLATE NOCASE OR file_name LIKE ? COLLATE NOCASE
                        OR path LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE
                        OR path LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE
                      )
                    ORDER BY id
                    LIMIT 4
                    """,
                    (
                        underscore,
                        f"{underscore}.%",
                        hyphen,
                        f"{hyphen}.%",
                        f"%/{underscore}.%",
                        f"%\\{underscore}.%",
                        f"%/{hyphen}.%",
                        f"%\\{hyphen}.%",
                    ),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to query exact-id Local Library candidates.") from exc
        return [self._row(row) for row in rows]

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            artists = json.loads(row[3] or "[]")
        except json.JSONDecodeError:
            artists = []
        try:
            metadata = json.loads(row[7] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": int(row[0]),
            "path": row[1],
            "title": row[2],
            "artists": artists if isinstance(artists, list) else [],
            "album": row[4],
            "duration_seconds": row[5],
            "codec": row[6],
            "metadata_json": metadata if isinstance(metadata, dict) else {},
            "tag_title_present": bool(isinstance(metadata, dict) and metadata.get("title")),
            "normalized_title": row[8] or "",
            "normalized_artists": row[9] or "",
            "duration_bucket": row[10],
            "modified_ns": row[11],
            "updated_at": row[12],
        }
