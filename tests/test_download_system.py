"""Tests for download-system queue, statuses and local import provider."""

from __future__ import annotations

import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from musicark.download.models import DownloadStatus
from musicark.download.provider import LocalImportProvider
from musicark.download.system import DownloadSystem
from musicark.storage.database import initialize_database


def create_sine_wav(path: Path, seconds: float = 0.5, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    amplitude = 16000
    frequency = 440.0
    total_samples = int(seconds * sample_rate)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for n in range(total_samples):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * (n / sample_rate)))
            frames.extend(struct.pack("<h", sample))
        wav_file.writeframes(bytes(frames))


class DownloadSystemTests(unittest.TestCase):
    def test_create_and_complete_local_import_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_file = root / "src.wav"
            create_sine_wav(src_file)
            target = root / "dest"
            db_path = root / "musicark.db"
            initialize_database(db_path)

            system = DownloadSystem(db_path)
            system.register_provider(LocalImportProvider())
            task = system.create_task(
                task_type="local_import",
                source_id=str(src_file),
                provider_id="local_import",
                target_folder=str(target),
            )
            done = system.run_task(task.id)

            self.assertEqual(done.status, DownloadStatus.COMPLETED)
            self.assertEqual(done.progress, 1.0)
            self.assertIsNotNone(done.result_local_file_id)

    def test_failed_task_can_be_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            initialize_database(db_path)
            system = DownloadSystem(db_path)
            system.register_provider(LocalImportProvider())

            task = system.create_task(
                task_type="local_import",
                source_id=str(root / "missing.wav"),
                provider_id="local_import",
                target_folder=str(root / "dest"),
            )
            failed = system.run_task(task.id)
            self.assertEqual(failed.status, DownloadStatus.FAILED)

            retried = system.retry_task(task.id)
            self.assertEqual(retried.status, DownloadStatus.QUEUED)
            self.assertIsNone(retried.error_message)

    def test_cancelled_task_remains_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_file = root / "src.wav"
            create_sine_wav(src_file)
            db_path = root / "musicark.db"
            initialize_database(db_path)

            system = DownloadSystem(db_path)
            system.register_provider(LocalImportProvider())
            task = system.create_task(
                task_type="local_import",
                source_id=str(src_file),
                provider_id="local_import",
                target_folder=str(root / "dest"),
            )
            cancelled = system.cancel_task(task.id)
            self.assertEqual(cancelled.status, DownloadStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
