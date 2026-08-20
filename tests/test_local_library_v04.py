"""MusicArk v0.4 Local Library scanner/storage regression tests."""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import wave

from musicark.local_library.metadata_reader import LocalMetadataReader
from musicark.local_library.models import LocalTrackMetadata
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository, normalize_local_path


class FakeMetadataReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def read(self, path: Path) -> LocalTrackMetadata:
        self.calls.append(str(path))
        if path.name == "broken.mp3":
            raise ValueError("corrupted")
        return LocalTrackMetadata(
            title=path.stem,
            artists=("Test Artist",),
            album="Test Album",
            duration_seconds=123.0,
            codec=path.suffix.lower().lstrip("."),
            bitrate=320000,
            sample_rate=44100,
        )


def write_file(path: Path, data: bytes = b"audio") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 800)


class LocalLibraryV04Tests(unittest.TestCase):
    def make_repo(self, temp: str) -> LocalLibraryStorageRepository:
        db_path = Path(temp) / ".musicark" / "musicark.db"
        initialize_database(db_path)
        return LocalLibraryStorageRepository(db_path)

    def test_empty_nested_supported_unsupported_and_unicode_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "Музыка тест"
            root_path.mkdir()
            repo = self.make_repo(tmp)
            root = repo.add_root(root_path)
            reader = FakeMetadataReader()
            scanner = LocalLibraryScanner(repo, reader)

            empty = scanner.scan(root)
            self.assertEqual(empty.as_dict(), {
                "added": 0, "updated": 0, "removed": 0, "unchanged": 0,
                "errors": 0, "scanned": 0, "errorItems": [],
            })

            write_file(root_path / "Артист" / "Альбом" / "трек.flac")
            write_file(root_path / "nested" / "song.mp3")
            write_file(root_path / "nested" / "notes.txt")
            result = scanner.scan(root)
            self.assertEqual(result.added, 2)
            self.assertEqual(result.errors, 0)
            self.assertEqual(len(reader.calls), 2)
            tracks, total = repo.list_tracks(limit=100, offset=0)
            self.assertEqual(total, 2)
            self.assertTrue(any(item["title"] == "трек" for item in tracks))
            self.assertTrue(all(not item["path"].endswith("notes.txt") for item in tracks))

    def test_missing_tags_fall_back_to_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Без тегов.wav"
            write_wav(path)
            metadata = LocalMetadataReader().read(path)
            self.assertEqual(metadata.title, "Без тегов")
            self.assertEqual(metadata.artists, ())
            self.assertGreater(metadata.duration_seconds or 0, 0)
            self.assertEqual(metadata.codec, "wav")

    def test_corrupted_file_isolated_from_good_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "music"
            write_file(root_path / "good.mp3")
            write_file(root_path / "broken.mp3")
            repo = self.make_repo(tmp)
            root = repo.add_root(root_path)
            result = LocalLibraryScanner(repo, FakeMetadataReader()).scan(root)
            self.assertEqual(result.added, 1)
            self.assertEqual(result.errors, 1)
            self.assertEqual(repo.local_stats()["total_files"], 1)
            self.assertIn("broken.mp3", result.error_items[0]["path"])

    def test_duplicate_and_overlapping_roots_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "Music"
            child = parent / "Rock"
            child.mkdir(parents=True)
            repo = self.make_repo(tmp)
            repo.add_root(parent)
            with self.assertRaises(ValueError):
                repo.add_root(parent)
            with self.assertRaises(ValueError):
                repo.add_root(child)
            self.assertEqual(normalize_local_path(parent), normalize_local_path(str(parent) + os.sep))

    def test_incremental_new_unchanged_modified_deleted_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "music"
            first = root_path / "first.mp3"
            write_file(first, b"one")
            repo = self.make_repo(tmp)
            root = repo.add_root(root_path)
            reader = FakeMetadataReader()
            scanner = LocalLibraryScanner(repo, reader)

            added = scanner.scan(root)
            self.assertEqual((added.added, added.updated, added.removed, added.unchanged), (1, 0, 0, 0))
            self.assertEqual(len(reader.calls), 1)

            unchanged = scanner.scan(root)
            self.assertEqual((unchanged.added, unchanged.updated, unchanged.removed, unchanged.unchanged), (0, 0, 0, 1))
            self.assertEqual(len(reader.calls), 1, "unchanged file must reuse stored metadata")

            old = first.stat().st_mtime_ns
            first.write_bytes(b"changed")
            os.utime(first, ns=(old + 2_000_000_000, old + 2_000_000_000))
            changed = scanner.scan(root)
            self.assertEqual((changed.added, changed.updated, changed.removed), (0, 1, 0))
            self.assertEqual(len(reader.calls), 2)

            second = root_path / "second.flac"
            write_file(second, b"two")
            plus_one = scanner.scan(root)
            self.assertEqual(plus_one.added, 1)
            self.assertEqual(plus_one.unchanged, 1)

            first.unlink()
            removed = scanner.scan(root)
            self.assertEqual(removed.removed, 1)
            tracks, total = repo.list_tracks(limit=100, offset=0)
            self.assertEqual(total, 1)
            self.assertEqual(tracks[0]["title"], "second")

            final = scanner.scan(root)
            self.assertEqual((final.added, final.updated, final.removed, final.unchanged), (0, 0, 0, 1))

    def test_root_removal_only_removes_index_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "music"
            audio = root_path / "keep.mp3"
            write_file(audio)
            repo = self.make_repo(tmp)
            root = repo.add_root(root_path)
            LocalLibraryScanner(repo, FakeMetadataReader()).scan(root)
            self.assertTrue(repo.remove_root(root.id))
            self.assertTrue(audio.exists(), "removing a root must never delete user files")
            self.assertEqual(repo.local_stats()["total_files"], 0)
            self.assertEqual(repo.list_roots(), [])

    def test_search_sort_and_pagination_storage_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "music"
            write_file(root_path / "Zulu.mp3")
            write_file(root_path / "Alpha.flac")
            repo = self.make_repo(tmp)
            root = repo.add_root(root_path)
            LocalLibraryScanner(repo, FakeMetadataReader()).scan(root)

            items, total = repo.list_tracks(limit=1, offset=0, sort="title")
            self.assertEqual(total, 2)
            self.assertEqual(items[0]["title"], "Alpha")
            second, _ = repo.list_tracks(limit=1, offset=1, sort="title")
            self.assertEqual(second[0]["title"], "Zulu")
            found, count = repo.list_tracks(limit=10, offset=0, search="zulu")
            self.assertEqual(count, 1)
            self.assertEqual(found[0]["fileName"], "Zulu.mp3")

    def test_v03_database_migrates_to_current_schema_and_preserves_yandex_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute("CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    conn.execute("INSERT INTO app_metadata(key, value) VALUES ('schema_version', '1.2.0')")
                    conn.execute("""
                        CREATE TABLE provider_collection_snapshots (
                            provider_id TEXT NOT NULL, collection_id TEXT NOT NULL,
                            account_json TEXT NOT NULL DEFAULT '{}', item_count INTEGER NOT NULL DEFAULT 0,
                            refreshed_at TEXT NOT NULL, collection_type TEXT NOT NULL DEFAULT 'liked',
                            external_id TEXT, title TEXT, owner_name TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
                            source_position INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
                            content_refreshed_at TEXT,
                            PRIMARY KEY(provider_id, collection_id)
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE provider_collection_items (
                            provider_id TEXT NOT NULL, collection_id TEXT NOT NULL, external_id TEXT NOT NULL,
                            position INTEGER NOT NULL, payload_json TEXT NOT NULL,
                            PRIMARY KEY(provider_id, collection_id, external_id)
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE local_audio_files (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE,
                            sha256 TEXT NOT NULL, file_size INTEGER NOT NULL, duration_seconds REAL,
                            codec TEXT NOT NULL, metadata_json TEXT,
                            created_at TEXT NOT NULL DEFAULT (datetime('now')),
                            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                        )
                    """)
                    conn.execute("INSERT INTO provider_collection_snapshots(provider_id, collection_id, account_json, item_count, refreshed_at, collection_type) VALUES ('yandex_music','liked','{}',1,'2026-08-14T00:00:00Z','liked')")
                    conn.execute("INSERT INTO provider_collection_items(provider_id, collection_id, external_id, position, payload_json) VALUES ('yandex_music','liked','101',0,'{\"title\":\"Keep me\"}')")

            initialize_database(db_path)
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
                liked = conn.execute("SELECT item_count FROM provider_collection_snapshots WHERE provider_id='yandex_music' AND collection_id='liked'").fetchone()
                item = conn.execute("SELECT payload_json FROM provider_collection_items WHERE external_id='101'").fetchone()
                roots = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='local_library_roots'").fetchone()
                download_settings = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='download_settings'").fetchone()
                columns = {row[1] for row in conn.execute("PRAGMA table_info(local_audio_files)")}
            self.assertEqual(version, "1.9.0")
            self.assertEqual(liked[0], 1)
            self.assertIn("Keep me", item[0])
            self.assertIsNotNone(roots)
            self.assertIsNotNone(download_settings)
            self.assertTrue({"normalized_path", "modified_ns", "title", "artists_json", "last_seen_at"}.issubset(columns))


if __name__ == "__main__":
    unittest.main()
