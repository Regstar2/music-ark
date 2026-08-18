"""Regression coverage for v0.9.7 large-library performance work."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from musicark.local_library.models import LocalLibraryRoot
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.local_library.service import LocalLibraryService
from musicark.metadata.artwork import ArtworkCache
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import normalize_local_path


class _NoArtworkReader:
    def __init__(self) -> None:
        self.calls = 0

    def artwork(self, path: Path):
        self.calls += 1
        return None


class _ScanDeltaRepository:
    def __init__(self, states: dict[str, dict]) -> None:
        self.states = states
        self.missing = None
        self.seen = None
        self.upserts = None

    def file_states(self, root_id: int) -> dict[str, dict]:
        return self.states

    def apply_scan(
        self,
        root_id: int,
        *,
        upserts,
        seen_normalized_paths,
        scanned_at: str,
        allow_removals: bool,
        missing_normalized_paths=None,
    ) -> int:
        self.upserts = list(upserts)
        self.seen = set(seen_normalized_paths)
        self.missing = set(missing_normalized_paths or ())
        return len(self.missing) if allow_removals else 0


class _PageRepository:
    def __init__(self) -> None:
        self.requested_limit = None

    def list_tracks(self, **kwargs):
        self.requested_limit = kwargs["limit"]
        return [], 5000


class LargeLibraryPerformanceV097Tests(unittest.TestCase):
    def test_missing_artwork_is_negative_cached_until_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / ".musicark" / "musicark.db"
            initialize_database(db_path)
            audio = root / "no-cover.mp3"
            audio.write_bytes(b"not-real-audio")

            cache = ArtworkCache(db_path, root)
            reader = _NoArtworkReader()
            cache._mp3 = reader
            row = {"id": 101, "path": str(audio), "source_external_id": None}

            first = cache.batch([row])
            second = cache.batch([row])

            self.assertFalse(first["101"]["present"])
            self.assertEqual(first["101"]["source"], "none")
            self.assertFalse(second["101"]["present"])
            self.assertEqual(reader.calls, 1, "unchanged no-cover files must not be reparsed")

            old_ns = audio.stat().st_mtime_ns
            audio.write_bytes(b"changed-file")
            os.utime(audio, ns=(old_ns + 2_000_000_000, old_ns + 2_000_000_000))
            cache.batch([row])
            self.assertEqual(reader.calls, 2, "file changes must invalidate the negative cache")

    def test_incremental_scan_passes_only_missing_paths_to_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "music"
            root_path.mkdir()
            live = root_path / "live.mp3"
            live.write_bytes(b"audio")
            live_state = live.stat()
            deleted = root_path / "deleted.mp3"

            live_key = normalize_local_path(live)
            deleted_key = normalize_local_path(deleted)
            repository = _ScanDeltaRepository(
                {
                    live_key: {
                        "id": 1,
                        "file_size": live_state.st_size,
                        "modified_ns": live_state.st_mtime_ns,
                        "sha256": "",
                    },
                    deleted_key: {
                        "id": 2,
                        "file_size": 5,
                        "modified_ns": 1,
                        "sha256": "",
                    },
                }
            )
            scanner = LocalLibraryScanner(repository)
            root = LocalLibraryRoot(
                id=1,
                path=str(root_path),
                normalized_path=normalize_local_path(root_path),
                enabled=True,
                created_at="2026-08-18T00:00:00Z",
            )

            result = scanner.scan(root)

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.removed, 1)
            self.assertEqual(repository.missing, {deleted_key})
            self.assertEqual(repository.seen, {live_key})
            self.assertEqual(repository.upserts, [])

    def test_track_page_is_bounded_for_large_ui_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            repository = _PageRepository()
            service = LocalLibraryService(
                database_path=db_path,
                repository=repository,
            )

            payload = service.tracks(limit=5000)

            self.assertEqual(repository.requested_limit, 250)
            self.assertEqual(payload["limit"], 250)
            self.assertEqual(payload["count"], 5000)


if __name__ == "__main__":
    unittest.main()
