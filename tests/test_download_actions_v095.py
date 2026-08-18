from __future__ import annotations

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from musicark.download.actions_bridge import DownloadTaskActions
from musicark.download.models import DownloadStatus, DownloadTask
from musicark.download.service import DownloadServiceError


class _FakeDownloads:
    def __init__(self, tasks: list[DownloadTask]) -> None:
        self.tasks = {task.id: task for task in tasks}

    def get_task(self, task_id: str) -> DownloadTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise DownloadServiceError("Download task is not found.", code="invalid_task")
        return task


class _FakeService:
    def __init__(self, database_path: Path, tasks: list[DownloadTask]) -> None:
        self._database_path = database_path
        self._downloads = _FakeDownloads(tasks)
        self.audit: list[tuple[str, str, str, str | None]] = []
        self.retry_calls: list[str] = []
        self.run_calls: list[str] = []
        self.cancel_calls: list[str] = []

    def retry(self, task_id: str) -> dict[str, object]:
        task = self._downloads.get_task(task_id)
        self.retry_calls.append(task_id)
        if task.status not in {DownloadStatus.FAILED, DownloadStatus.NEEDS_REVIEW}:
            raise DownloadServiceError("Task is not retryable.", code="not_retryable")
        task.status = DownloadStatus.QUEUED
        task.error_code = None
        task.error_message = None
        return {"task": self._task_payload(task)}

    def run_task(self, task_id: str) -> DownloadTask:
        task = self._downloads.get_task(task_id)
        self.run_calls.append(task_id)
        if task.status != DownloadStatus.QUEUED:
            raise DownloadServiceError("Task is not queued.", code="invalid_state")
        task.status = DownloadStatus.COMPLETED
        return task

    def cancel(self, task_id: str) -> dict[str, object]:
        task = self._downloads.get_task(task_id)
        self.cancel_calls.append(task_id)
        if task.status == DownloadStatus.QUEUED:
            task.status = DownloadStatus.CANCELLED
        elif task.status == DownloadStatus.RUNNING:
            task.cancel_requested = True
        return {"task": self._task_payload(task)}

    def enqueue(self, external_id: str) -> dict[str, object]:
        task = DownloadTask(
            id=f"selected-{external_id}",
            task_type="provider_download",
            source_id=external_id,
            provider_id="yandex_music_download",
            target_folder=str(self._database_path.parent),
            status=DownloadStatus.QUEUED,
            raw_payload={
                "source_provider_id": "yandex_music",
                "title": f"Track {external_id}",
                "artists": ["Artist"],
            },
        )
        self._downloads.tasks[task.id] = task
        return {"created": True, "task": self._task_payload(task)}

    def _audit_event(
        self,
        event_type: str,
        status: str,
        details: str,
        task_id: str | None = None,
    ) -> None:
        self.audit.append((event_type, status, details, task_id))

    @staticmethod
    def _task_payload(task: DownloadTask) -> dict[str, object]:
        return {
            "id": task.id,
            "externalId": task.source_id,
            "provider": "yandex_music",
            "status": task.status.value,
            "errorCode": task.error_code,
            "error": task.error_message,
        }


class DownloadActionsV095Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "musicark.db"
        with sqlite3.connect(self.database) as conn:
            conn.execute(
                "CREATE TABLE download_tasks (id TEXT PRIMARY KEY, task_type TEXT NOT NULL)"
            )

    def _task(
        self,
        task_id: str,
        status: DownloadStatus,
        *,
        task_type: str = "provider_download",
        filename: str = "track.mp3",
    ) -> DownloadTask:
        task = DownloadTask(
            id=task_id,
            task_type=task_type,
            source_id=f"source-{task_id}",
            provider_id="yandex_music_download",
            target_folder=str(self.root),
            status=status,
            raw_payload={
                "source_provider_id": "yandex_music",
                "target_filename": filename,
                "direct_request": False,
            },
        )
        with sqlite3.connect(self.database) as conn:
            conn.execute(
                "INSERT INTO download_tasks(id, task_type) VALUES(?, ?)",
                (task.id, task.task_type),
            )
        return task

    def _row_exists(self, task_id: str) -> bool:
        with sqlite3.connect(self.database) as conn:
            row = conn.execute(
                "SELECT 1 FROM download_tasks WHERE id=?", (task_id,)
            ).fetchone()
        return row is not None

    def test_remove_failed_deletes_task_and_partial_but_not_final_file(self) -> None:
        task = self._task("failed-1", DownloadStatus.FAILED)
        final_file = self.root / "track.mp3"
        partial_file = self.root / "track.mp3.part"
        final_file.write_bytes(b"final-audio")
        partial_file.write_bytes(b"partial")
        service = _FakeService(self.database, [task])

        result = DownloadTaskActions(service).remove_tasks([task.id])

        self.assertEqual(result["succeeded"], 1)
        self.assertFalse(self._row_exists(task.id))
        self.assertTrue(final_file.exists())
        self.assertFalse(partial_file.exists())
        self.assertEqual(service.audit[0][0], "download_task_removed")
        self.assertEqual(service.audit[0][3], task.id)

    def test_remove_needs_review_never_deletes_existing_final_file(self) -> None:
        task = self._task("review-1", DownloadStatus.NEEDS_REVIEW, filename="review.mp3")
        final_file = self.root / "review.mp3"
        final_file.write_bytes(b"review-audio")
        service = _FakeService(self.database, [task])

        result = DownloadTaskActions(service).remove_tasks([task.id])

        self.assertEqual(result["failed"], 0)
        self.assertFalse(self._row_exists(task.id))
        self.assertTrue(final_file.exists())

    def test_active_task_cannot_be_removed(self) -> None:
        task = self._task("queued-1", DownloadStatus.QUEUED)
        service = _FakeService(self.database, [task])

        result = DownloadTaskActions(service).remove_tasks([task.id])

        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"][0]["code"], "not_removable")
        self.assertTrue(self._row_exists(task.id))
        self.assertEqual(service.audit, [])

    def test_internal_task_cannot_be_removed_through_user_actions(self) -> None:
        task = self._task(
            "legacy-1",
            DownloadStatus.FAILED,
            task_type="legacy_download",
        )
        service = _FakeService(self.database, [task])

        result = DownloadTaskActions(service).remove_tasks([task.id])

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"][0]["code"], "invalid_task")
        self.assertTrue(self._row_exists(task.id))

    def test_bulk_remove_reports_invalid_id_without_touching_unrelated_rows(self) -> None:
        first = self._task("failed-1", DownloadStatus.FAILED, filename="one.mp3")
        second = self._task("queued-1", DownloadStatus.QUEUED, filename="two.mp3")
        service = _FakeService(self.database, [first, second])

        result = DownloadTaskActions(service).remove_tasks(
            [first.id, "missing-task", second.id]
        )

        self.assertEqual(result["requested"], 3)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 2)
        self.assertFalse(self._row_exists(first.id))
        self.assertTrue(self._row_exists(second.id))
        error_codes = {error["code"] for error in result["errors"]}
        self.assertEqual(error_codes, {"invalid_task", "not_removable"})

    def test_partial_cleanup_rejects_path_escape(self) -> None:
        task = self._task(
            "failed-escape",
            DownloadStatus.FAILED,
            filename="../outside.mp3",
        )
        outside_partial = self.root.parent / "outside.mp3.part"
        outside_partial.write_bytes(b"must-stay")
        self.addCleanup(lambda: outside_partial.unlink(missing_ok=True))
        service = _FakeService(self.database, [task])

        result = DownloadTaskActions(service).remove_tasks([task.id])

        self.assertEqual(result["succeeded"], 1)
        self.assertTrue(outside_partial.exists())

    def test_bulk_retry_does_not_run_unrelated_or_any_queued_task(self) -> None:
        failed = self._task("failed-1", DownloadStatus.FAILED)
        unrelated = self._task("queued-old", DownloadStatus.QUEUED, filename="old.mp3")
        service = _FakeService(self.database, [failed, unrelated])

        result = DownloadTaskActions(service).retry_tasks([failed.id])

        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(service.retry_calls, [failed.id])
        self.assertEqual(service.run_calls, [])
        self.assertEqual(failed.status, DownloadStatus.QUEUED)
        self.assertEqual(unrelated.status, DownloadStatus.QUEUED)

    def test_enqueue_selected_returns_only_requested_tasks(self) -> None:
        service = _FakeService(self.database, [])

        result = DownloadTaskActions(service).enqueue_selected(["101", "102", "101"])

        self.assertEqual(result["requested"], 2)
        self.assertEqual(
            [item["id"] for item in result["items"]],
            ["selected-101", "selected-102"],
        )


if __name__ == "__main__":
    unittest.main()
