"""Maintain SQL-indexed normalized local metadata for matching runs."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError
from .normalize import artists_key, normalize_text


class LocalMatchIndex:
    """Refresh compact normalized columns once per matching run.

    This is deliberately O(Local) once per run, never O(Yandex × Local). It keeps the
    matching index correct even when v0.4 rescans update structured metadata without
    knowing anything about v0.5 matching internals.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def refresh(self) -> int:
        changed: list[tuple[str, str, int | None, int]] = []
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, path, title, artists_json, duration_seconds,
                           normalized_title, normalized_artists_text, duration_bucket
                    FROM local_audio_files
                    WHERE availability='available'
                    ORDER BY id
                    """
                ).fetchall()
                for row in rows:
                    file_id = int(row[0])
                    path = str(row[1] or "")
                    title = row[2]
                    try:
                        artists = json.loads(row[3] or "[]")
                    except json.JSONDecodeError:
                        artists = []
                    if not isinstance(artists, list):
                        artists = []
                    normalized_title = normalize_text(title or Path(path).stem)
                    normalized_artists = artists_key(str(item) for item in artists if item)
                    duration_bucket = (
                        int(round(float(row[4]))) // 5 if row[4] is not None else None
                    )
                    if (
                        normalized_title != str(row[5] or "")
                        or normalized_artists != str(row[6] or "")
                        or duration_bucket != row[7]
                    ):
                        changed.append(
                            (normalized_title, normalized_artists, duration_bucket, file_id)
                        )
                if changed:
                    with conn:
                        conn.executemany(
                            """
                            UPDATE local_audio_files
                            SET normalized_title=?, normalized_artists_text=?, duration_bucket=?
                            WHERE id=?
                            """,
                            changed,
                        )
        except sqlite3.Error as exc:
            raise StorageError("Failed to refresh the local matching index.") from exc
        return len(changed)
