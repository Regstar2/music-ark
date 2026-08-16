from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.download.models import DownloadStatus, DownloadTask
from musicark.storage.database import initialize_database
from musicark.storage.download_storage import DownloadStorageRepository


class DownloadRecoveryV07Tests(unittest.TestCase):
    def test_interrupted_running_task_cleans_part_and_becomes_retryable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / ".musicark" / "musicark.db"
            target = root / "Music" / "MusicArk"
            target.mkdir(parents=True)
            initialize_database(database)
            filename = "Artist - Track [yandex_99].mp3"
            partial = target / f"{filename}.part"
            partial.write_bytes(b"partial")

            repository = DownloadStorageRepository(database)
            task = DownloadTask(
                task_type="provider_download",
                source_id="99",
                provider_id="yandex_music_download",
                target_folder=str(target),
                status=DownloadStatus.RUNNING,
                raw_payload={"track_id": "99", "target_filename": filename},
            )
            repository.upsert_task(task)

            self.assertEqual(repository.recover_interrupted(), 1)
            recovered = repository.get_task(task.id)
            self.assertEqual(recovered.status, DownloadStatus.FAILED)
            self.assertEqual(recovered.error_code, "interrupted")
            self.assertFalse(recovered.cancel_requested)
            self.assertFalse(partial.exists())
            self.assertFalse((target / filename).exists())

    def test_recovery_refuses_part_path_traversal_from_legacy_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / ".musicark" / "musicark.db"
            target = root / "Music" / "MusicArk"
            target.mkdir(parents=True)
            outside = target.parent / "outside.mp3.part"
            outside.write_bytes(b"must-survive")
            initialize_database(database)

            repository = DownloadStorageRepository(database)
            task = DownloadTask(
                task_type="provider_download",
                source_id="100",
                provider_id="yandex_music_download",
                target_folder=str(target),
                status=DownloadStatus.RUNNING,
                raw_payload={"track_id": "100", "target_filename": "../outside.mp3"},
            )
            repository.upsert_task(task)

            repository.recover_interrupted()
            self.assertTrue(outside.exists())
            self.assertEqual(outside.read_bytes(), b"must-survive")


if __name__ == "__main__":
    unittest.main()
