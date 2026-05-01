"""Tests for v1.0 SyncSafeExecutor (no network when Yandex execute is patched)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from musicark.providers.models import LocalAudioFile
from musicark.download.provider import YandexMusicDownloadProvider
from musicark.storage.database import initialize_database
from musicark.storage.sync_storage import SyncStorageRepository
from musicark.sync.models import SyncOperation, SyncOperationType, SyncPlan
from musicark.sync.safe_execution import SyncSafeExecutor


class SyncSafeExecutorTests(unittest.TestCase):
    def test_execute_confirm_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            db_path = base_dir / ".musicark" / "musicark.db"
            initialize_database(db_path)
            ex = SyncSafeExecutor(database_path=db_path, base_dir=base_dir)
            with self.assertRaises(ValueError):
                ex.execute_safe_plan_operations(plan_id=None, confirm=False)

    def test_skips_non_create_download_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            db_path = base_dir / ".musicark" / "musicark.db"
            initialize_database(db_path)

            dl_dir = base_dir / "downloads"
            plan = SyncPlan(
                id="plan-a",
                operations=[
                    SyncOperation(
                        operation_type=SyncOperationType.DOWNLOAD_TRACK,
                        entity_id="1",
                        reason="legacy",
                        is_dangerous=False,
                    ),
                ],
                summary={"n": 1},
            )
            SyncStorageRepository(db_path).save_plan(plan)

            ex = SyncSafeExecutor(database_path=db_path, base_dir=base_dir)
            result = ex.execute_safe_plan_operations(plan_id="plan-a", confirm=True)
            self.assertEqual(result["summary"]["executed_count"], 0)
            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["skipped"][0]["reason"], "not_executable_in_safe_v1")

    def test_runs_safe_yandex_download_task_with_mocked_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            db_path = base_dir / ".musicark" / "musicark.db"
            initialize_database(db_path)
            dl_dir = base_dir / "downloads"
            dl_dir.mkdir(parents=True)

            def fake_execute(self, task):  # noqa: ANN001
                outp = Path(task.target_folder) / f"yandex-{task.source_id}.mp3"
                outp.parent.mkdir(parents=True, exist_ok=True)
                outp.write_bytes(b"x")
                return LocalAudioFile(
                    path=str(outp),
                    sha256="a" * 64,
                    file_size=1,
                    duration_seconds=None,
                    codec="mp3",
                    metadata_json={},
                )

            plan = SyncPlan(
                id="plan-y",
                operations=[
                    SyncOperation(
                        operation_type=SyncOperationType.CREATE_DOWNLOAD_TASK,
                        entity_id="999001",
                        reason="fixture",
                        is_dangerous=False,
                        metadata={
                            "task_type": "yandex_download",
                            "provider_id": "yandex_music_download",
                            "source_id": "999001",
                            "target_folder": str(dl_dir),
                            "quality": "best",
                        },
                    ),
                ],
                summary={"n": 1},
            )
            SyncStorageRepository(db_path).save_plan(plan)

            with patch.object(YandexMusicDownloadProvider, "execute", autospec=True, side_effect=fake_execute):
                ex = SyncSafeExecutor(database_path=db_path, base_dir=base_dir)
                result = ex.execute_safe_plan_operations(plan_id="plan-y", confirm=True)

            self.assertEqual(result["summary"]["executed_count"], 1)
            self.assertEqual(result["errors"], [])
            self.assertEqual(len(result["executed"]), 1)
            self.assertEqual(result["executed"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
