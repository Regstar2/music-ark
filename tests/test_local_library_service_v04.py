"""Application-service resilience tests for MusicArk v0.4 Local Library."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.local_library.models import LocalTrackMetadata
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.local_library.service import LocalLibraryService
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


class MetadataReader:
    def read(self, path: Path) -> LocalTrackMetadata:
        return LocalTrackMetadata(
            title=path.stem,
            artists=("Artist",),
            duration_seconds=60.0,
            codec=path.suffix.lower().lstrip("."),
        )


class LocalLibraryServiceV04Tests(unittest.TestCase):
    def test_scan_all_continues_when_one_root_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            db_path = base / ".musicark" / "musicark.db"
            initialize_database(db_path)
            repository = LocalLibraryStorageRepository(db_path)

            missing_root = base / "a-missing"
            healthy_root = base / "b-healthy"
            missing_root.mkdir()
            healthy_root.mkdir()
            missing = repository.add_root(missing_root)
            healthy = repository.add_root(healthy_root)
            (healthy_root / "track.mp3").write_bytes(b"fixture")
            missing_root.rmdir()

            scanner = LocalLibraryScanner(repository, MetadataReader())
            service = LocalLibraryService(
                base_dir=base,
                repository=repository,
                scanner=scanner,
            )
            result = service.scan()

            self.assertEqual(result["errors"], 1)
            self.assertEqual(result["added"], 1)
            self.assertEqual(len(result["roots"]), 2)
            self.assertTrue(any(item["rootId"] == missing.id and item["errors"] == 1 for item in result["roots"]))
            self.assertTrue(any(item["rootId"] == healthy.id and item["added"] == 1 for item in result["roots"]))
            self.assertIn("a-missing", result["errorItems"][0]["path"])


if __name__ == "__main__":
    unittest.main()
