"""Storage repository for download tasks."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError
from musicark.download.models import DownloadStatus, DownloadTask


class DownloadStorageRepository:
    """Persists and retrieves download-task queue state."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def upsert_task(self, task: DownloadTask) -> None:
        raw_payload_json = json.dumps(task.raw_payload, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO download_tasks(
                            id, task_type, source_id, provider_id, status, progress, target_folder,
                            created_at, started_at, finished_at, error_message, result_local_file_id, raw_payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            task_type=excluded.task_type,
                            source_id=excluded.source_id,
                            provider_id=excluded.provider_id,
                            status=excluded.status,
                            progress=excluded.progress,
                            target_folder=excluded.target_folder,
                            started_at=excluded.started_at,
                            finished_at=excluded.finished_at,
                            error_message=excluded.error_message,
                            result_local_file_id=excluded.result_local_file_id,
                            raw_payload_json=excluded.raw_payload_json
                        """,
                        (
                            task.id,
                            task.task_type,
                            task.source_id,
                            task.provider_id,
                            task.status.value,
                            task.progress,
                            task.target_folder,
                            task.created_at,
                            task.started_at,
                            task.finished_at,
                            task.error_message,
                            task.result_local_file_id,
                            raw_payload_json,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist download task.") from exc

    def get_task(self, task_id: str) -> DownloadTask:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT id, task_type, source_id, provider_id, status, progress, target_folder,
                           created_at, started_at, finished_at, error_message, result_local_file_id, raw_payload_json
                    FROM download_tasks
                    WHERE id=?
                    """,
                    (task_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read download task.") from exc
        if row is None:
            raise StorageError(f"Download task '{task_id}' is not found.")
        return self._row_to_task(row)

    def list_tasks(self) -> list[DownloadTask]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, task_type, source_id, provider_id, status, progress, target_folder,
                           created_at, started_at, finished_at, error_message, result_local_file_id, raw_payload_json
                    FROM download_tasks
                    ORDER BY created_at
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list download tasks.") from exc
        return [self._row_to_task(row) for row in rows]

    def _row_to_task(self, row) -> DownloadTask:  # type: ignore[no-untyped-def]
        raw_payload = json.loads(row[12] or "{}")
        return DownloadTask(
            id=row[0],
            task_type=row[1],
            source_id=row[2],
            provider_id=row[3],
            status=DownloadStatus(row[4]),
            progress=float(row[5]),
            target_folder=row[6],
            created_at=row[7] or datetime.now(UTC).isoformat(),
            started_at=row[8],
            finished_at=row[9],
            error_message=row[10],
            result_local_file_id=row[11],
            raw_payload=raw_payload,
        )
