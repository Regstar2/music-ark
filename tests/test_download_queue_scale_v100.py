"""v1.0 acceptance regressions for large persisted download queues."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.download.bridge import _user_summary
from musicark.storage.database import initialize_database


class _SummaryServiceStub:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @staticmethod
    def settings() -> dict[str, object]:
        return {
            "targetConfigured": True,
            "rootId": 1,
            "rootPath": "C:/Music",
            "targetPath": "C:/Music",
        }


class DownloadQueueScaleV100Tests(unittest.TestCase):
    def test_summary_counts_all_user_tasks_beyond_legacy_5000_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            now = datetime.now(UTC).isoformat()
            rows = [
                (
                    f"task-{index}",
                    "provider_download",
                    str(index),
                    "yandex_music_download",
                    "queued",
                    0.0,
                    str(Path(tmp) / "downloads"),
                    now,
                    "{}",
                )
                for index in range(5_247)
            ]
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO download_tasks(
                            id, task_type, source_id, provider_id, status, progress,
                            target_folder, created_at, raw_payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )

            summary = _user_summary(_SummaryServiceStub(db))  # type: ignore[arg-type]

            self.assertEqual(summary["counts"]["queued"], 5_247)
            self.assertEqual(summary["counts"]["total"], 5_247)


if __name__ == "__main__":
    unittest.main()
