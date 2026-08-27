"""Connection-reusing candidate generation for large-library matching runs.

This module keeps matching semantics aligned with :mod:`musicark.matching.candidates`
while removing per-track SQLite connection setup and repeated legacy exact-ID scans.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from musicark.core.errors import StorageError

from .normalize import artists_key, normalize_text
from .policy import CANDIDATE_LIMIT

_ACTIVE_ROOT_CLAUSE = """
    AND (
        NOT EXISTS (SELECT 1 FROM local_library_roots WHERE enabled=1)
        OR library_root_id IN (SELECT id FROM local_library_roots WHERE enabled=1)
    )
"""
_ALLOWED_EXACT_ROOT_CLAUSE = """
    (
        (NOT EXISTS (SELECT 1 FROM local_library_roots WHERE enabled=1)
         AND availability IN ('available', 'legacy'))
        OR
        (availability='available'
         AND library_root_id IN (SELECT id FROM local_library_roots WHERE enabled=1))
    )
"""
_EXACT_FILENAME = re.compile(r"^yandex[_-](\d+)(?:\.|$)", re.IGNORECASE)


class ResponsiveCandidateGenerator:
    """Generate bounded candidates through one SQLite connection per matching run."""

    def __init__(self, connection: sqlite3.Connection, *, limit: int = CANDIDATE_LIMIT) -> None:
        self._connection = connection
        self._limit = max(1, int(limit))
        self.comparison_count = 0
        self._exact_by_external_id = self._preload_exact_candidates()

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

        def add_rows(sql: str, params: list[Any]) -> None:
            remaining = page_limit - len(found)
            if remaining <= 0:
                return
            for row in self._connection.execute(sql, [*params, remaining]).fetchall():
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
            if normalized_title:
                add_rows(
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

    def _preload_exact_candidates(self) -> dict[str, list[dict[str, Any]]]:
        """Build legacy/trusted Yandex exact-ID lookup once instead of once per track."""
        columns = """
            id, path, title, artists_json, album, duration_seconds, codec,
            metadata_json, normalized_title, normalized_artists_text,
            duration_bucket, modified_ns, updated_at,
            source_provider_id, source_external_id, file_name
        """
        try:
            rows = self._connection.execute(
                f"""
                SELECT {columns}
                FROM local_audio_files
                WHERE {_ALLOWED_EXACT_ROOT_CLAUSE}
                  AND (
                    source_provider_id='yandex_music'
                    OR LOWER(COALESCE(file_name, '')) GLOB 'yandex_*'
                    OR LOWER(COALESCE(file_name, '')) GLOB 'yandex-*'
                  )
                ORDER BY id
                """
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to preload exact-id Local Library candidates.") from exc

        by_id: dict[str, list[dict[str, Any]]] = {}

        def add(external_id: str, item: dict[str, Any]) -> None:
            clean = str(external_id or "").strip()
            if not clean:
                return
            bucket = by_id.setdefault(clean, [])
            file_id = int(item["id"])
            if any(int(existing["id"]) == file_id for existing in bucket):
                return
            if len(bucket) < 4:
                bucket.append(item)

        for row in rows:
            item = self._row(row[:13])
            item["source_provider_id"] = row[13]
            item["source_external_id"] = row[14]
            if str(row[13] or "") == "yandex_music":
                add(str(row[14] or ""), item)
            match = _EXACT_FILENAME.match(str(row[15] or ""))
            if match is not None:
                add(match.group(1), item)
        return by_id

    def _exact_id_candidates(self, provider: dict[str, Any]) -> list[dict[str, Any]]:
        if provider.get("provider_id") != "yandex_music":
            return []
        external_id = str(provider.get("external_id") or "").strip()
        if not external_id:
            return []
        return list(self._exact_by_external_id.get(external_id, ()))

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
