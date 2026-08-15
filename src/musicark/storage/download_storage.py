"""SQLite persistence for the MusicArk v0.7 download queue."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.download.models import DownloadStatus, DownloadTask


_SENSITIVE_PAYLOAD_PARTS = ("token", "authorization", "cookie", "direct_url", "direct_link")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_safe_payload(value: Any, path: str = "raw_payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in _SENSITIVE_PAYLOAD_PARTS):
                raise StorageError(f"Sensitive download data cannot be persisted in {path}.{key}.")
            _validate_safe_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_safe_payload(child, f"{path}[{index}]")


class DownloadStorageRepository:
    """Persist tasks, target settings and cooperative cancellation state."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def upsert_task(self, task: DownloadTask) -> None:
        _validate_safe_payload(task.raw_payload)
        task.updated_at = _now()
        raw_payload_json = json.dumps(task.raw_payload, ensure_ascii=False)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO download_tasks(
                            id, task_type, source_id, provider_id, status, progress, target_folder,
                            created_at, started_at, finished_at, error_message, result_local_file_id,
                            raw_payload_json, downloaded_bytes, total_bytes, cancel_requested,
                            target_root_id, error_code, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            raw_payload_json=excluded.raw_payload_json,
                            downloaded_bytes=excluded.downloaded_bytes,
                            total_bytes=excluded.total_bytes,
                            cancel_requested=excluded.cancel_requested,
                            target_root_id=excluded.target_root_id,
                            error_code=excluded.error_code,
                            updated_at=excluded.updated_at
                        """,
                        (
                            task.id,
                            task.task_type,
                            task.source_id,
                            task.provider_id,
                            task.status.value,
                            float(task.progress),
                            task.target_folder,
                            task.created_at,
                            task.started_at,
                            task.finished_at,
                            task.error_message,
                            task.result_local_file_id,
                            raw_payload_json,
                            int(task.downloaded_bytes),
                            task.total_bytes,
                            1 if task.cancel_requested else 0,
                            task.target_root_id,
                            task.error_code,
                            task.updated_at,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist download task.") from exc

    def get_task(self, task_id: str) -> DownloadTask:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(self._select_sql() + " WHERE id=?", (task_id,)).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read download task.") from exc
        if row is None:
            raise StorageError(f"Download task '{task_id}' is not found.")
        return self._row_to_task(row)

    def list_tasks(self, status: str = "", limit: int = 1000) -> list[DownloadTask]:
        clean = status.strip().casefold()
        where = " WHERE status=?" if clean else ""
        params: list[Any] = [clean] if clean else []
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    self._select_sql() + where + " ORDER BY created_at DESC LIMIT ?",
                    [*params, max(1, min(int(limit), 5000))],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list download tasks.") from exc
        return [self._row_to_task(row) for row in rows]

    def find_active(self, provider_id: str, source_id: str) -> DownloadTask | None:
        return self._find_identity(provider_id, source_id, ("queued", "running"))

    def find_retryable(self, provider_id: str, source_id: str) -> DownloadTask | None:
        return self._find_identity(provider_id, source_id, ("failed", "needs_review", "cancelled"))

    def _find_identity(
        self, provider_id: str, source_id: str, statuses: tuple[str, ...]
    ) -> DownloadTask | None:
        placeholders = ",".join("?" for _ in statuses)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    self._select_sql()
                    + f" WHERE provider_id=? AND source_id=? AND status IN ({placeholders})"
                    + " ORDER BY created_at DESC LIMIT 1",
                    [provider_id, source_id, *statuses],
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to inspect download queue identity.") from exc
        return self._row_to_task(row) if row else None

    def update_progress(self, task_id: str, downloaded_bytes: int, total_bytes: int | None) -> None:
        downloaded = max(0, int(downloaded_bytes))
        total = int(total_bytes) if total_bytes is not None and int(total_bytes) >= 0 else None
        progress = min(1.0, downloaded / total) if total and total > 0 else 0.0
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        UPDATE download_tasks
                        SET downloaded_bytes=?, total_bytes=?, progress=?, updated_at=?
                        WHERE id=?
                        """,
                        (downloaded, total, progress, _now(), task_id),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist download progress.") from exc

    def request_cancel(self, task_id: str) -> DownloadTask:
        task = self.get_task(task_id)
        if task.status == DownloadStatus.QUEUED:
            task.cancel_requested = True
            task.status = DownloadStatus.CANCELLED
            task.error_code = "cancelled"
            task.error_message = "Cancelled before download started."
            task.finished_at = _now()
            self.upsert_task(task)
            return task
        if task.status == DownloadStatus.RUNNING:
            task.cancel_requested = True
            self.upsert_task(task)
        return task

    def is_cancel_requested(self, task_id: str) -> bool:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT cancel_requested FROM download_tasks WHERE id=?", (task_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read cancellation state.") from exc
        return bool(row and row[0])

    def recover_interrupted(self) -> int:
        """Turn persisted RUNNING tasks into retryable failures after process restart."""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE download_tasks
                        SET status='failed', error_code='interrupted',
                            error_message='Download was interrupted by application shutdown.',
                            finished_at=?, updated_at=?, cancel_requested=0
                        WHERE status='running'
                        """,
                        (_now(), _now()),
                    )
                    return max(0, int(cursor.rowcount))
        except sqlite3.Error as exc:
            raise StorageError("Failed to recover interrupted downloads.") from exc

    def summary(self) -> dict[str, int]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT status, COUNT(*) FROM download_tasks GROUP BY status"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to summarize download queue.") from exc
        counts = {str(status): int(count) for status, count in rows}
        return {
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0) + counts.get("needs_review", 0),
            "cancelled": counts.get("cancelled", 0),
            "skipped": counts.get("skipped", 0),
            "total": sum(counts.values()),
        }

    def clear_completed(self) -> int:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute("DELETE FROM download_tasks WHERE status='completed'")
                    return max(0, int(cursor.rowcount))
        except sqlite3.Error as exc:
            raise StorageError("Failed to clear completed download history.") from exc

    def get_target_root_id(self) -> int | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT value FROM download_settings WHERE key='target_root_id'"
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read download target setting.") from exc
        if not row:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None

    def set_target_root_id(self, root_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO download_settings(key, value, updated_at)
                        VALUES('target_root_id', ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                        """,
                        (str(int(root_id)), _now()),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist download target setting.") from exc

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT id, task_type, source_id, provider_id, status, progress, target_folder,
                   created_at, started_at, finished_at, error_message, result_local_file_id,
                   raw_payload_json, downloaded_bytes, total_bytes, cancel_requested,
                   target_root_id, error_code, updated_at
            FROM download_tasks
        """

    @staticmethod
    def _row_to_task(row: tuple[Any, ...]) -> DownloadTask:
        try:
            raw_payload = json.loads(row[12] or "{}")
        except json.JSONDecodeError:
            raw_payload = {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        try:
            status = DownloadStatus(row[4])
        except ValueError:
            status = DownloadStatus.FAILED
        return DownloadTask(
            id=str(row[0]),
            task_type=str(row[1]),
            source_id=str(row[2]),
            provider_id=str(row[3]),
            status=status,
            progress=float(row[5] or 0),
            target_folder=str(row[6]),
            created_at=str(row[7] or _now()),
            started_at=row[8],
            finished_at=row[9],
            error_message=row[10],
            result_local_file_id=row[11],
            raw_payload=raw_payload,
            downloaded_bytes=int(row[13] or 0),
            total_bytes=int(row[14]) if row[14] is not None else None,
            cancel_requested=bool(row[15]),
            target_root_id=int(row[16]) if row[16] is not None else None,
            error_code=row[17],
            updated_at=str(row[18] or row[7] or _now()),
        )
