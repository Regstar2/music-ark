from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.download import bridge
from musicark.download.models import DownloadStatus, DownloadTask
from musicark.storage.database import initialize_database


class _ListService:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items

    def tasks(self, *, status: str = "", limit: int = 1000):  # type: ignore[no-untyped-def]
        items = self.items
        if status:
            items = [item for item in items if item.get("status") == status]
        return {"count": len(items), "items": items[:limit]}


class _DbService:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path


class _CoverageStub:
    def __init__(self, *, status: str = "missing", action: str = "unreviewed") -> None:
        self.item = {
            "providerId": "yandex_music",
            "externalId": "203",
            "coverageStatus": status,
            "userAction": action,
            "provider": {
                "title": "Missing Track",
                "artists": ["Artist"],
                "duration_seconds": 120,
            },
        }

    def get_track(self, *, provider_id: str, external_id: str):  # type: ignore[no-untyped-def]
        if provider_id != "yandex_music" or external_id != "203":
            return None
        return dict(self.item)


class _DownloadRepoStub:
    def __init__(self) -> None:
        self.saved: DownloadTask | None = None

    def upsert_task(self, task: DownloadTask) -> None:
        self.saved = task


class _DirectServiceStub:
    SOURCE_PROVIDER = "yandex_music"

    def __init__(self) -> None:
        self._coverage = _CoverageStub()
        self._downloads = _DownloadRepoStub()
        self.seen_action: str | None = None

    def _enqueue_track(self, track):  # type: ignore[no-untyped-def]
        self.seen_action = track.get("userAction")
        task = DownloadTask(
            task_type="provider_download",
            source_id="203",
            provider_id="yandex_music_download",
            target_folder="C:/Music",
            status=DownloadStatus.QUEUED,
            raw_payload={"source_provider_id": "yandex_music"},
        )
        return task, True

    def _task_payload(self, task: DownloadTask) -> dict[str, object]:
        return {"id": task.id, "status": task.status.value}


class DownloadBridgeV07IsolationTests(unittest.TestCase):
    def test_user_items_hide_legacy_reference_cache_rows(self) -> None:
        service = _ListService(
            [
                {
                    "id": "user",
                    "provider": "yandex_music",
                    "downloadProvider": "yandex_music_download",
                    "status": "completed",
                },
                {
                    "id": "reference",
                    "provider": "yandex_music_download",
                    "downloadProvider": "yandex_music_download",
                    "status": "completed",
                },
            ]
        )

        visible = bridge._user_items(service)  # type: ignore[arg-type]
        self.assertEqual([item["id"] for item in visible], ["user"])
        self.assertEqual(bridge._summary_counts(visible)["completed"], 1)
        self.assertEqual(bridge._summary_counts(visible)["total"], 1)

    def test_clear_completed_deletes_only_v07_user_task_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(database)
            with closing(sqlite3.connect(database)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO download_tasks(
                            id, task_type, source_id, provider_id, status,
                            target_folder, created_at, updated_at
                        ) VALUES
                            ('user', 'provider_download', '1', 'yandex_music_download',
                             'completed', 'C:/Music', 'now', 'now'),
                            ('reference', 'yandex_download', '1', 'yandex_music_download',
                             'completed', '.musicark/downloads/yandex', 'now', 'now')
                        """
                    )

            result = bridge._user_clear_completed(_DbService(database))  # type: ignore[arg-type]
            self.assertEqual(result["removed"], 1)

            with closing(sqlite3.connect(database)) as conn:
                remaining = conn.execute(
                    "SELECT id, task_type FROM download_tasks ORDER BY id"
                ).fetchall()
            self.assertEqual(remaining, [("reference", "yandex_download")])

    def test_direct_enqueue_does_not_persist_fake_wanted_triage(self) -> None:
        service = _DirectServiceStub()

        result = bridge._direct_enqueue(service, "203")  # type: ignore[arg-type]

        self.assertTrue(result["created"])
        self.assertEqual(service.seen_action, "wanted", "legacy service gate sees explicit intent")
        self.assertEqual(service._coverage.item["userAction"], "unreviewed")
        self.assertIsNotNone(service._downloads.saved)
        self.assertTrue(service._downloads.saved.raw_payload["direct_request"])

    def test_direct_coverage_proxy_only_overrides_missing_action_in_memory(self) -> None:
        source = _CoverageStub(status="missing", action="ignored")
        proxy = bridge._DirectCoverageProxy(source, "203")

        view = proxy.get_track(provider_id="yandex_music", external_id="203")
        self.assertEqual(view["userAction"], "wanted")
        self.assertEqual(source.item["userAction"], "ignored")

        source.item["coverageStatus"] = "covered"
        covered = proxy.get_track(provider_id="yandex_music", external_id="203")
        self.assertEqual(covered["userAction"], "ignored")


if __name__ == "__main__":
    unittest.main()
