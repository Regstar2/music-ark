from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.download import bridge
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


if __name__ == "__main__":
    unittest.main()
