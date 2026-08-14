"""Paginated matching-result queries kept separate from write persistence."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError


class MatchingResultQueries:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_results(
        self,
        *,
        provider_id: str,
        limit: int,
        offset: int,
        status: str,
        search: str,
        sort: str,
    ) -> tuple[list[dict[str, Any]], int]:
        page_limit = max(1, min(int(limit), 500))
        page_offset = max(0, int(offset))
        where = ["mr.provider_id=?"]
        params: list[Any] = [provider_id]
        if status in {"matched", "conflict", "unmatched"}:
            where.append("mr.status=?")
            params.append(status)
        query = search.strip()
        if query:
            needle = f"%{query}%"
            where.append(
                "(json_extract(pt.payload_json,'$.title') LIKE ? COLLATE NOCASE "
                "OR json_extract(pt.payload_json,'$.artists') LIKE ? COLLATE NOCASE "
                "OR COALESCE(laf.title,'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(laf.artists_json,'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(laf.path,'') LIKE ? COLLATE NOCASE)"
            )
            params.extend([needle, needle, needle, needle, needle])
        order_by = {
            "confidence": "mr.confidence DESC, mr.external_id",
            "artist": "json_extract(pt.payload_json,'$.artists[0]') COLLATE NOCASE, json_extract(pt.payload_json,'$.title') COLLATE NOCASE",
            "title": "json_extract(pt.payload_json,'$.title') COLLATE NOCASE, mr.external_id",
            "status": "mr.status, mr.confidence DESC, json_extract(pt.payload_json,'$.title') COLLATE NOCASE",
        }.get(sort, "mr.confidence DESC, mr.external_id")
        where_sql = " AND ".join(where)
        base_from = """
            FROM matching_results mr
            JOIN provider_tracks pt
              ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
            LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
        """
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) {base_from} WHERE {where_sql}",
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    f"""
                    SELECT mr.provider_id, mr.external_id, mr.status, mr.local_file_id,
                           mr.confidence, mr.method, mr.score_breakdown_json, mr.reason,
                           mr.manual, mr.updated_at, pt.payload_json,
                           laf.path, laf.title, laf.artists_json, laf.album, laf.duration_seconds
                    {base_from}
                    WHERE {where_sql}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_limit, page_offset],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list matching results.") from exc
        return [self._row(row) for row in rows], total

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            provider = json.loads(row[10] or "{}")
        except json.JSONDecodeError:
            provider = {}
        try:
            local_artists = json.loads(row[13] or "[]")
        except json.JSONDecodeError:
            local_artists = []
        try:
            score = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            score = {}
        local = None
        if row[3] is not None:
            local = {
                "id": int(row[3]),
                "path": row[11],
                "title": row[12],
                "artists": local_artists if isinstance(local_artists, list) else [],
                "album": row[14],
                "durationSeconds": row[15],
            }
        return {
            "providerId": row[0],
            "externalId": row[1],
            "status": row[2],
            "localFileId": row[3],
            "confidence": float(row[4] or 0),
            "method": row[5],
            "score": score if isinstance(score, dict) else {},
            "reason": row[7],
            "manual": bool(row[8]),
            "updatedAt": row[9],
            "provider": provider if isinstance(provider, dict) else {},
            "local": local,
        }
