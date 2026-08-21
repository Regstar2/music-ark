"""EXPLAIN QUERY PLAN audit for MusicArk v0.14 hot read paths."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from musicark.coverage.sql import coverage_base_cte
from musicark.storage.database import initialize_database


def _details(conn: sqlite3.Connection, sql: str, params: list[Any]) -> list[str]:
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return [str(row[3]) for row in rows]


def audit_queries(database_path: Path | None = None) -> dict[str, list[str]]:
    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if database_path is None:
        owned_temp = tempfile.TemporaryDirectory()
        database_path = Path(owned_temp.name) / "musicark-query-audit.db"
        initialize_database(database_path)

    try:
        with closing(sqlite3.connect(database_path)) as conn:
            # Coverage's CTE references deterministic SQL UDFs. Query planning does
            # not need their real values, but SQLite must know the functions exist.
            conn.create_function(
                "musicark_provider_fingerprint", 3, lambda *_args: "", deterministic=True
            )
            conn.create_function(
                "musicark_local_fingerprint", 8, lambda *_args: "", deterministic=True
            )

            coverage_sql = coverage_base_cte() + """
                SELECT provider_id, external_id, coverage_status
                FROM coverage_base
                WHERE coverage_status=?
                ORDER BY COALESCE(json_extract(payload_json,'$.artists[0]'),'') COLLATE NOCASE,
                         COALESCE(json_extract(payload_json,'$.title'),'') COLLATE NOCASE,
                         external_id
                LIMIT ? OFFSET ?
            """

            audits = {
                "localLibraryList": (
                    """
                    SELECT id, title FROM local_audio_files
                    WHERE availability='available' AND library_root_id IS NOT NULL
                    ORDER BY COALESCE(artists_json, '[]') COLLATE NOCASE,
                             title COLLATE NOCASE
                    LIMIT ? OFFSET ?
                    """,
                    [250, 0],
                ),
                "localLibrarySearch": (
                    """
                    SELECT id, title FROM local_audio_files
                    WHERE availability='available' AND library_root_id IS NOT NULL
                      AND (title LIKE ? COLLATE NOCASE
                           OR artists_json LIKE ? COLLATE NOCASE
                           OR COALESCE(album,'') LIKE ? COLLATE NOCASE
                           OR file_name LIKE ? COLLATE NOCASE)
                    ORDER BY title COLLATE NOCASE, path COLLATE NOCASE
                    LIMIT ? OFFSET ?
                    """,
                    ["%needle%", "%needle%", "%needle%", "%needle%", 250, 0],
                ),
                "localLibraryRootFilter": (
                    """
                    SELECT id, title FROM local_audio_files
                    WHERE availability='available' AND library_root_id=?
                    ORDER BY path COLLATE NOCASE
                    LIMIT ? OFFSET ?
                    """,
                    [1, 250, 0],
                ),
                "providerCollections": (
                    """
                    SELECT collection_id, collection_type, external_id, title,
                           item_count, source_position
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND active=1
                    ORDER BY CASE WHEN collection_id='liked' THEN 0 ELSE 1 END,
                             source_position, title COLLATE NOCASE
                    """,
                    ["yandex_music"],
                ),
                "matchingResults": (
                    """
                    SELECT mr.provider_id, mr.external_id, mr.status, mr.confidence
                    FROM matching_results mr
                    JOIN provider_tracks pt
                      ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                    LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                    WHERE mr.provider_id=?
                    ORDER BY mr.confidence DESC, mr.external_id
                    LIMIT ? OFFSET ?
                    """,
                    ["yandex_music", 50, 0],
                ),
                "coverageResults": (
                    coverage_sql,
                    ["yandex_music", "", 3, "", "missing", 100, 0],
                ),
                "downloadsList": (
                    """
                    SELECT id, source_id, provider_id, status, created_at
                    FROM download_tasks
                    WHERE status=?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    ["failed", 250],
                ),
            }
            return {
                name: _details(conn, sql, params)
                for name, (sql, params) in audits.items()
            }
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = {"schema": 1, "queries": audit_queries(args.database)}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
