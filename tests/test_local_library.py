"""Tests for local library recursive scanning and persistence."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import math
import sqlite3
import struct
import tempfile
import unittest
import wave

from musicark.providers.local_library import LocalLibraryProvider, calculate_sha256
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


def create_sine_wav(path: Path, seconds: float = 0.5, sample_rate: int = 44100) -> None:
    """Create deterministic wav test audio."""
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


class LocalLibraryTests(unittest.TestCase):
    def test_recursive_scan_indexes_audio_and_ignores_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "music"
            create_sine_wav(root / "a.wav")
            create_sine_wav(root / "nested" / "b.wav")
            (root / "notes.txt").write_text("not audio", encoding="utf-8")

            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider = LocalLibraryProvider()

            result = provider.scan(root, db_path)
            self.assertEqual(result["indexed"], 2)
            self.assertEqual(result["failed"], 0)

            with closing(sqlite3.connect(db_path)) as conn:
                local_count = conn.execute("SELECT COUNT(*) FROM local_audio_files").fetchone()[0]
                source_count = conn.execute(
                    "SELECT COUNT(*) FROM track_sources WHERE provider_id='local_library'"
                ).fetchone()[0]
            self.assertEqual(local_count, 2)
            self.assertEqual(source_count, 2)

    def test_repeat_scan_does_not_create_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "music"
            audio_file = root / "song.wav"
            create_sine_wav(audio_file)

            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider = LocalLibraryProvider()

            provider.scan(root, db_path)
            provider.scan(root, db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                local_count = conn.execute("SELECT COUNT(*) FROM local_audio_files").fetchone()[0]
                source_count = conn.execute(
                    "SELECT COUNT(*) FROM track_sources WHERE provider_id='local_library'"
                ).fetchone()[0]
                audit_count = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE event_type='local_scan'"
                ).fetchone()[0]

            self.assertEqual(local_count, 1)
            self.assertEqual(source_count, 1)
            self.assertEqual(audit_count, 2)

    def test_sha256_is_stable_for_same_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.wav"
            create_sine_wav(path)
            hash_one = calculate_sha256(path)
            hash_two = calculate_sha256(path)
            self.assertEqual(hash_one, hash_two)

    def test_local_stats_reports_codec_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "music"
            create_sine_wav(root / "one.wav")
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider = LocalLibraryProvider()
            provider.scan(root, db_path)

            storage = LocalLibraryStorageRepository(db_path)
            stats = storage.local_stats()
            self.assertEqual(stats["total_files"], 1)
            self.assertEqual(stats["by_codec"].get("wav"), 1)


if __name__ == "__main__":
    unittest.main()
