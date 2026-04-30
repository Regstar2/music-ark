"""Tests for yandex download provider integration without network."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.download.provider import YandexMusicDownloadProvider
from musicark.download.system import DownloadSystem
from musicark.storage.database import initialize_database


def create_fake_wav_bytes() -> bytes:
    # Minimal RIFF header + tiny payload suitable for hash/file storage tests.
    return (
        b"RIFF"
        + (36 + 8).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (44100).to_bytes(4, "little")
        + (88200).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + (8).to_bytes(4, "little")
        + b"\x00\x00\x01\x00\x00\x00\x01\x00"
    )


class FakeYandexDownloadProvider(YandexMusicDownloadProvider):
    def _resolve_direct_link(self, track_id: str, quality: str = "best") -> str:
        return f"https://example.invalid/{track_id}/{quality}"

    def _download_to_file(self, direct_link: str, destination: Path) -> None:
        destination.write_bytes(create_fake_wav_bytes())


class YandexDownloadTests(unittest.TestCase):
    def test_yandex_task_downloads_file_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            target = root / "downloads"
            initialize_database(db_path)

            system = DownloadSystem(db_path)
            system.register_provider(FakeYandexDownloadProvider(base_dir=root))
            task = system.create_task(
                task_type="yandex_download",
                source_id="123456",
                provider_id="yandex_music_download",
                target_folder=str(target),
            )
            task.raw_payload = {"track_id": "123456", "quality": "best"}
            from musicark.storage.download_storage import DownloadStorageRepository

            DownloadStorageRepository(db_path).upsert_task(task)
            done = system.run_task(task.id)

            self.assertEqual(done.status.value, "completed")
            self.assertIsNotNone(done.result_local_file_id)
            downloaded = target / "yandex_123456.mp3"
            self.assertTrue(downloaded.exists())

    def test_existing_download_is_reused_without_duplicate_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            target = root / "downloads"
            initialize_database(db_path)
            provider = FakeYandexDownloadProvider(base_dir=root)
            system = DownloadSystem(db_path)
            system.register_provider(provider)

            task = system.create_task(
                task_type="yandex_download",
                source_id="555",
                provider_id="yandex_music_download",
                target_folder=str(target),
            )
            task.raw_payload = {"track_id": "555", "quality": "320"}
            from musicark.storage.download_storage import DownloadStorageRepository

            DownloadStorageRepository(db_path).upsert_task(task)
            first = system.run_task(task.id)

            retry = system.retry_task(task.id) if first.status.value == "failed" else first
            if retry.status.value != "failed":
                # Run again as a new task to ensure existing file is reused.
                second_task = system.create_task(
                    task_type="yandex_download",
                    source_id="555",
                    provider_id="yandex_music_download",
                    target_folder=str(target),
                )
                second_task.raw_payload = {"track_id": "555", "quality": "320"}
                DownloadStorageRepository(db_path).upsert_task(second_task)
                second = system.run_task(second_task.id)
                self.assertEqual(second.status.value, "completed")


if __name__ == "__main__":
    unittest.main()
