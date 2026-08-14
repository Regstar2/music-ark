"""Bounded SQL-backed candidate generation for MusicArk v0.5."""

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


class CandidateGenerator:
    """Generate a small plausible local set before expensive similarity scoring."""

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
            for candidate in self._repository.find_local_candidates(
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
                    """
                    SELECT id, path, title, artists_json, album, duration_seconds, codec,
                           metadata_json, normalized_title, normalized_artists_text,
                           duration_bucket, modified_ns, updated_at
                    FROM local_audio_files
                    WHERE availability IN ('available', 'legacy')
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
            raise StorageError("Failed to query exact-id matching candidates.") from exc
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
