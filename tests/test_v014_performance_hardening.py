"""Deterministic regression coverage for MusicArk v0.14 performance hardening."""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from musicark.local_library.models import LocalLibraryRoot
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.local_library.service import LocalLibraryService
from musicark.metadata.artwork import ArtworkCache
from musicark.storage.database import CURRENT_SCHEMA_VERSION, initialize_database
from musicark.storage.local_library_storage import (
    LocalLibraryStorageRepository,
    normalize_local_path,
)


class _PageRepository:
    def __init__(self) -> None:
        self.requested_limit: int | None = None

    def list_tracks(self, **kwargs):  # type: ignore[no-untyped-def]
        self.requested_limit = int(kwargs["limit"])
        return [], 50_000


class _ScanRepository:
    def __init__(self, states: dict[str, dict]) -> None:
        self.states = states
        self.upserts = None
        self.missing = None
        self.seen = None
        self.allow_removals = None

    def file_states(self, root_id: int) -> dict[str, dict]:
        return self.states

    def apply_scan(
        self,
        root_id: int,
        *,
        upserts,
        seen_normalized_paths,
        missing_normalized_paths=None,
        allow_removals: bool,
        **kwargs,
    ) -> int:
        self.upserts = list(upserts)
        self.seen = set(seen_normalized_paths)
        self.missing = set(missing_normalized_paths or ())
        self.allow_removals = allow_removals
        return len(self.missing) if allow_removals else 0


class _CountingReader:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, path: Path):
        self.calls += 1
        raise AssertionError("unchanged files must not be reparsed")


class _NoArtworkAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def artwork(self, path: Path):
        self.calls += 1
        if self.fail:
            raise ValueError("corrupt artwork")
        return None


class _FixedRegistry:
    def __init__(self, adapter: _NoArtworkAdapter) -> None:
        self.adapter = adapter

    def adapter_for(self, path: Path):
        return self.adapter


def _insert_track(
    conn: sqlite3.Connection,
    *,
    root_id: int,
    path: str,
    modified_ns: int,
    last_seen_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO local_audio_files(
            library_root_id, path, normalized_path, file_name, extension,
            sha256, file_size, modified_ns, duration_seconds, codec,
            metadata_json, title, artists_json, album, availability, last_seen_at
        ) VALUES (?, ?, ?, ?, '.mp3', '', 10, ?, 180, 'mp3', '{}', ?, '["Artist"]', 'Album', 'available', ?)
        """,
        (
            root_id,
            path,
            path.replace("\\", "/").casefold(),
            Path(path).name,
            modified_ns,
            Path(path).stem,
            last_seen_at,
        ),
    )


class PerformanceHardeningV014Tests(unittest.TestCase):
    def test_backend_caps_oversized_local_library_pages_at_250(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            repository = _PageRepository()
            service = LocalLibraryService(database_path=db_path, repository=repository)  # type: ignore[arg-type]
            payload = service.tracks(limit=5000)
            self.assertEqual(repository.requested_limit, 250)
            self.assertEqual(payload["limit"], 250)
            self.assertEqual(payload["count"], 50_000)

    def test_unchanged_scan_has_zero_metadata_reads_and_zero_upserts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "Музыка с пробелами"
            root_path.mkdir()
            states: dict[str, dict] = {}
            for index in range(40):
                path = root_path / f"трек {index:03d}.mp3"
                path.touch()
                stat = path.stat()
                states[normalize_local_path(path)] = {
                    "id": index + 1,
                    "file_size": stat.st_size,
                    "modified_ns": stat.st_mtime_ns,
                    "sha256": "",
                }
            repository = _ScanRepository(states)
            reader = _CountingReader()
            scanner = LocalLibraryScanner(repository, metadata_reader=reader)  # type: ignore[arg-type]
            root = LocalLibraryRoot(
                id=1,
                path=str(root_path),
                normalized_path=normalize_local_path(root_path),
                enabled=True,
                created_at="2026-08-21T00:00:00Z",
            )
            result = scanner.scan(root)
            self.assertEqual(result.unchanged, 40)
            self.assertEqual(result.added, 0)
            self.assertEqual(result.updated, 0)
            self.assertEqual(result.removed, 0)
            self.assertEqual(reader.calls, 0)
            self.assertEqual(repository.upserts, [])
            self.assertEqual(repository.missing, set())

    def test_partial_walk_failure_never_reports_missing_paths_for_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp) / "root"
            root_path.mkdir()
            live = root_path / "live.mp3"
            live.touch()
            missing = root_path / "uncertain.mp3"
            stat = live.stat()
            states = {
                normalize_local_path(live): {
                    "id": 1,
                    "file_size": stat.st_size,
                    "modified_ns": stat.st_mtime_ns,
                    "sha256": "",
                },
                normalize_local_path(missing): {
                    "id": 2,
                    "file_size": 1,
                    "modified_ns": 1,
                    "sha256": "",
                },
            }
            repository = _ScanRepository(states)
            scanner = LocalLibraryScanner(repository, metadata_reader=_CountingReader())  # type: ignore[arg-type]
            root = LocalLibraryRoot(
                id=1,
                path=str(root_path),
                normalized_path=normalize_local_path(root_path),
                enabled=True,
                created_at="2026-08-21T00:00:00Z",
            )

            def incomplete_walk(path, *, topdown, followlinks, onerror):  # type: ignore[no-untyped-def]
                onerror(PermissionError(13, "denied", str(root_path / "blocked")))
                yield str(root_path), [], [live.name]

            with patch("musicark.local_library.scanner.os.walk", incomplete_walk):
                result = scanner.scan(root)

            self.assertEqual(result.errors, 1)
            self.assertFalse(repository.allow_removals)
            self.assertEqual(repository.missing, set())
            self.assertEqual(result.removed, 0)

    def test_delta_storage_does_not_rewrite_unchanged_last_seen_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    root_id = int(
                        conn.execute(
                            "INSERT INTO local_library_roots(path, normalized_path) VALUES ('C:/Music', 'c:/music')"
                        ).lastrowid
                    )
                    _insert_track(
                        conn,
                        root_id=root_id,
                        path="C:/Music/keep.mp3",
                        modified_ns=1,
                        last_seen_at="old-keep",
                    )
                    _insert_track(
                        conn,
                        root_id=root_id,
                        path="C:/Music/delete.mp3",
                        modified_ns=1,
                        last_seen_at="old-delete",
                    )
            repository = LocalLibraryStorageRepository(db_path)
            removed = repository.apply_scan(
                root_id,
                upserts=[],
                seen_normalized_paths={"c:/music/keep.mp3"},
                missing_normalized_paths={"c:/music/delete.mp3"},
                scanned_at="new-scan",
                allow_removals=True,
            )
            self.assertEqual(removed, 1)
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT last_seen_at FROM local_audio_files WHERE normalized_path='c:/music/keep.mp3'"
                ).fetchone()
                self.assertEqual(row, ("old-keep",))
                root_scan = conn.execute(
                    "SELECT last_scanned_at FROM local_library_roots WHERE id=?",
                    (root_id,),
                ).fetchone()
                self.assertEqual(root_scan, ("new-scan",))

    def test_negative_artwork_cache_is_multiformat_and_invalidates_on_fingerprint_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            initialize_database(db_path)
            audio = root / "no-cover.flac"
            audio.write_bytes(b"fake-flac")
            cache = ArtworkCache(db_path, root)
            adapter = _NoArtworkAdapter()
            cache._adapters = _FixedRegistry(adapter)  # type: ignore[attr-defined]
            row = {"id": 77, "path": str(audio), "source_external_id": None}
            first = cache.batch([row])
            second = cache.batch([row])
            self.assertFalse(first["77"]["present"])
            self.assertEqual(first["77"]["source"], "none")
            self.assertFalse(second["77"]["present"])
            self.assertEqual(adapter.calls, 1)

            # Same size but new mtime invalidates the negative cache.
            previous = audio.stat().st_mtime_ns
            audio.write_bytes(b"fake-flac")
            os.utime(audio, ns=(previous + 2_000_000_000, previous + 2_000_000_000))
            cache.batch([row])
            self.assertEqual(adapter.calls, 2)

            # A trusted provider identity is part of the cache fingerprint as well.
            provider_row = {
                "id": 77,
                "path": str(audio),
                "source_external_id": "yandex-1",
            }
            cache.batch([provider_row])
            cache.batch([provider_row])
            self.assertEqual(adapter.calls, 3)
            provider_row["source_external_id"] = "yandex-2"
            cache.batch([provider_row])
            self.assertEqual(adapter.calls, 4)

            # Size changes also invalidate even if the path identity stays stable.
            audio.write_bytes(b"different-size")
            cache.batch([provider_row])
            self.assertEqual(adapter.calls, 5)

    def test_corrupt_artwork_is_isolated_and_becomes_negative_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            initialize_database(db_path)
            audio = root / "broken-art.opus"
            audio.write_bytes(b"synthetic-opus")
            cache = ArtworkCache(db_path, root)
            adapter = _NoArtworkAdapter(fail=True)
            cache._adapters = _FixedRegistry(adapter)  # type: ignore[attr-defined]
            payload = cache.batch([{"id": 91, "path": str(audio), "source_external_id": None}])
            self.assertFalse(payload["91"]["present"])
            self.assertEqual(payload["91"]["source"], "none")
            self.assertEqual(adapter.calls, 1)
            cache.batch([{"id": 91, "path": str(audio), "source_external_id": None}])
            self.assertEqual(adapter.calls, 1)

    def test_cached_artwork_page_uses_one_batch_sqlite_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "musicark.db"
            initialize_database(db_path)
            cache = ArtworkCache(db_path, root)
            rows = []
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    for index in range(12):
                        audio = root / f"track-{index}.flac"
                        audio.write_bytes(b"x")
                        fingerprint = cache._fingerprint(audio, None)  # type: ignore[attr-defined]
                        conn.execute(
                            """
                            INSERT INTO local_artwork_cache(
                                local_file_id, fingerprint, cache_path, source, updated_at
                            ) VALUES (?, ?, '', 'none', datetime('now'))
                            """,
                            (index + 1, fingerprint),
                        )
                        rows.append({"id": index + 1, "path": str(audio), "source_external_id": None})

            real_connect = sqlite3.connect
            calls = 0

            def counting_connect(*args, **kwargs):  # type: ignore[no-untyped-def]
                nonlocal calls
                calls += 1
                return real_connect(*args, **kwargs)

            with patch("musicark.metadata.artwork.sqlite3.connect", counting_connect):
                payload = cache.batch(rows)
            self.assertEqual(len(payload), 12)
            self.assertEqual(calls, 1)

    def test_database_init_reopen_is_idempotent_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()
            self.assertEqual(version, (CURRENT_SCHEMA_VERSION,))

    def test_representative_precurrent_upgrade_preserves_existing_user_rows(self) -> None:
        """v0.14 has no new schema; re-running the existing forward chain is safe."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    root_id = int(
                        conn.execute(
                            "INSERT INTO local_library_roots(path, normalized_path) VALUES (?, ?)",
                            ("D:/Музыка Existing", "d:/музыка existing"),
                        ).lastrowid
                    )
                    _insert_track(
                        conn,
                        root_id=root_id,
                        path="D:/Музыка Existing/keep.mp3",
                        modified_ns=123,
                        last_seen_at="preserve-me",
                    )
                    conn.execute(
                        """
                        INSERT INTO provider_track_actions(provider_id, external_id, action)
                        VALUES ('yandex_music', 'existing-track', 'wanted')
                        """
                    )
                    conn.execute(
                        "UPDATE app_metadata SET value='1.8.4' WHERE key='schema_version'"
                    )

            initialize_database(db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()
                local = conn.execute(
                    "SELECT path, last_seen_at FROM local_audio_files WHERE normalized_path=?",
                    ("d:/музыка existing/keep.mp3",),
                ).fetchone()
                action = conn.execute(
                    """
                    SELECT action FROM provider_track_actions
                    WHERE provider_id='yandex_music' AND external_id='existing-track'
                    """
                ).fetchone()
            self.assertEqual(version, (CURRENT_SCHEMA_VERSION,))
            self.assertEqual(local, ("D:/Музыка Existing/keep.mp3", "preserve-me"))
            self.assertEqual(action, ("wanted",))


if __name__ == "__main__":
    unittest.main()
