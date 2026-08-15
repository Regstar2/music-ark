from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from musicark.coverage.repository import CoverageRepository
from musicark.download.models import DownloadStatus, DownloadTask
from musicark.download.provider import (
    DownloadCancelledError,
    DownloadProvider,
    DownloadProviderError,
    YandexMusicDownloadProvider,
    sanitize_filename,
    yandex_download_filename,
)
from musicark.download.service import DownloadService, DownloadServiceError
from musicark.download.system import DownloadProviderRegistry
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.policy import MATCHER_VERSION
from musicark.providers.local_library import build_local_audio_file
from musicark.storage.database import initialize_database
from musicark.storage.download_migration import migrate_download_v07
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.storage.matching_storage import MatchingStorageRepository


PROVIDER = "yandex_music"
DOWNLOAD_PROVIDER = "yandex_music_download"


class _FakeDownloadProvider(DownloadProvider):
    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls = 0

    @property
    def provider_id(self) -> str:
        return DOWNLOAD_PROVIDER

    def execute(self, task: DownloadTask):  # type: ignore[no-untyped-def]
        return self.execute_with_context(task)

    def execute_with_context(self, task, *, progress=None, cancelled=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise DownloadProviderError("offline", code="network_error")
        target = Path(task.target_folder)
        target.mkdir(parents=True, exist_ok=True)
        path = target / str(task.raw_payload["target_filename"])
        if cancelled is not None and cancelled():
            raise DownloadCancelledError()
        if progress is not None:
            progress(512, 1024)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b"\x00\x00" * 8000)
        if progress is not None:
            progress(path.stat().st_size, path.stat().st_size)
        return build_local_audio_file(path)


class DownloadV07Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        self.music = self.root / "Music"
        self.music.mkdir()
        initialize_database(self.db)
        self._snapshot("liked", "Мне нравится")

    def _snapshot(self, collection_id: str, title: str) -> None:
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO provider_collection_snapshots(
                    provider_id, collection_id, account_json, item_count, refreshed_at,
                    collection_type, external_id, title, metadata_json, source_position, active
                ) VALUES (?, ?, '{}', 0, datetime('now'), ?, ?, ?, '{}', 0, 1)
                """,
                (
                    PROVIDER,
                    collection_id,
                    "liked" if collection_id == "liked" else "playlist",
                    None if collection_id == "liked" else collection_id.split(":", 1)[-1],
                    title,
                ),
            )

    def _member(
        self,
        external_id: str,
        *,
        collection_id: str = "liked",
        storage_id: str | None = None,
        title: str = "Track",
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "provider_id": PROVIDER,
            "external_id": external_id,
            "title": title,
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 1.0,
        }
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO provider_collection_items(
                    provider_id, collection_id, external_id, position, payload_json
                ) VALUES (?, ?, ?, 0, ?)
                """,
                (PROVIDER, collection_id, storage_id or external_id, json.dumps(payload)),
            )
            conn.execute(
                """
                INSERT INTO provider_tracks(provider_id, external_id, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(provider_id, external_id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                (PROVIDER, external_id, json.dumps(payload)),
            )
            conn.execute(
                """
                UPDATE provider_collection_snapshots SET item_count=item_count+1
                WHERE provider_id=? AND collection_id=?
                """,
                (PROVIDER, collection_id),
            )
        return payload

    def _matching(self, external_id: str, payload: dict[str, object], status: str) -> None:
        local_fp = MatchingStorageRepository(self.db).local_library_fingerprint()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO matching_results(
                    provider_id, external_id, status, local_file_id, confidence, method,
                    reason, matcher_version, provider_fingerprint, local_fingerprint, manual
                ) VALUES (?, ?, ?, NULL, 0, 'automatic', 'test', ?, ?, ?, 0)
                """,
                (
                    PROVIDER,
                    external_id,
                    status,
                    MATCHER_VERSION,
                    provider_fingerprint(PROVIDER, external_id, payload),
                    local_fp,
                ),
            )

    def _action(self, external_id: str, action: str) -> None:
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO provider_track_actions(provider_id, external_id, action) VALUES (?, ?, ?)",
                (PROVIDER, external_id, action),
            )

    def _service(self, provider: DownloadProvider | None = None) -> DownloadService:
        registry = DownloadProviderRegistry()
        registry.register(provider or _FakeDownloadProvider())
        return DownloadService(base_dir=self.root, registry=registry)

    def _seed_missing_wanted(self, external_id: str = "101") -> dict[str, object]:
        payload = self._member(external_id, title=f"Track {external_id}")
        self._matching(external_id, payload, "unmatched")
        self._action(external_id, "wanted")
        return payload

    def test_missing_wanted_download_becomes_normal_covered_local_track(self) -> None:
        self._seed_missing_wanted("101")
        service = self._service()
        settings = service.set_target(str(self.music))
        self.assertEqual(settings["rootPath"], str(self.music.resolve()))

        queued = service.enqueue("101")
        self.assertTrue(queued["created"])
        task = queued["task"]
        self.assertEqual(task["status"], "queued")
        self.assertIn("[yandex_101]", task["targetPath"])

        result = service.run()
        self.assertEqual(result["processed"], 1)
        completed = DownloadStorageRepository(self.db).get_task(task["id"])
        self.assertEqual(completed.status, DownloadStatus.COMPLETED)
        self.assertIsNotNone(completed.result_local_file_id)

        with sqlite3.connect(self.db) as conn:
            local = conn.execute(
                "SELECT library_root_id, normalized_path, availability FROM local_audio_files WHERE id=?",
                (completed.result_local_file_id,),
            ).fetchone()
            link = conn.execute(
                """
                SELECT match_method FROM track_links
                WHERE source_provider_id=? AND source_external_id=? AND local_file_id=?
                """,
                (PROVIDER, "101", completed.result_local_file_id),
            ).fetchone()
            variant_count = conn.execute(
                "SELECT COUNT(*) FROM track_variant_results WHERE provider_id=? AND external_id=?",
                (PROVIDER, "101"),
            ).fetchone()[0]
        self.assertIsNotNone(local[0])
        self.assertTrue(local[1])
        self.assertEqual(local[2], "available")
        self.assertEqual(link[0], "exact_id")
        self.assertEqual(variant_count, 0, "Download must not fabricate Variant SAME")

        covered = CoverageRepository(self.db).get_track(provider_id=PROVIDER, external_id="101")
        self.assertEqual(covered["coverageStatus"], "covered")
        self.assertEqual(covered["method"], "exact_id")
        self.assertEqual(covered["userAction"], "wanted", "wanted is retained as history")
        listed, total = LocalLibraryStorageRepository(self.db).list_tracks(limit=10, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(listed[0]["id"], completed.result_local_file_id)

    def test_duplicate_memberships_and_repeat_enqueue_create_one_active_task(self) -> None:
        self._snapshot("playlist:a", "Playlist A")
        payload = self._member("42", title="Once")
        self._member("42", collection_id="playlist:a", storage_id="42::duplicate:1", title="Once")
        self._matching("42", payload, "unmatched")
        self._action("42", "wanted")
        service = self._service()
        service.set_target(str(self.music))
        first = service.enqueue("42")
        second = service.enqueue("42")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["task"]["id"], second["task"]["id"])
        self.assertEqual(len(DownloadStorageRepository(self.db).list_tasks()), 1)

    def test_eligibility_rejects_ignored_unreviewed_conflict_and_not_analyzed(self) -> None:
        service = self._service()
        service.set_target(str(self.music))

        ignored = self._member("1", title="Ignored")
        self._matching("1", ignored, "unmatched")
        self._action("1", "ignored")
        with self.assertRaises(DownloadServiceError) as cm:
            service.enqueue("1")
        self.assertEqual(cm.exception.code, "not_eligible")

        unreviewed = self._member("2", title="Unreviewed")
        self._matching("2", unreviewed, "unmatched")
        with self.assertRaises(DownloadServiceError):
            service.enqueue("2")

        conflict = self._member("3", title="Conflict")
        self._matching("3", conflict, "conflict")
        self._action("3", "wanted")
        with self.assertRaises(DownloadServiceError):
            service.enqueue("3")

        self._member("4", title="Not analyzed")
        self._action("4", "wanted")
        with self.assertRaises(DownloadServiceError):
            service.enqueue("4")

    def test_failed_download_remains_missing_wanted_and_retry_can_succeed(self) -> None:
        self._seed_missing_wanted("301")
        provider = _FakeDownloadProvider(fail_first=True)
        service = self._service(provider)
        service.set_target(str(self.music))
        task_id = service.enqueue("301")["task"]["id"]
        first = service.run()["items"][0]
        self.assertEqual(first["status"], "failed")
        self.assertEqual(first["errorCode"], "network_error")
        track = CoverageRepository(self.db).get_track(provider_id=PROVIDER, external_id="301")
        self.assertEqual(track["coverageStatus"], "missing")
        self.assertEqual(track["userAction"], "wanted")

        service.retry(task_id)
        second = service.run()["items"][0]
        self.assertEqual(second["status"], "completed")
        files = list((self.music / "MusicArk").glob("*"))
        self.assertEqual(len(files), 1)

    def test_recheck_skips_task_if_track_became_ineligible_before_run(self) -> None:
        self._seed_missing_wanted("401")
        service = self._service()
        service.set_target(str(self.music))
        task_id = service.enqueue("401")["task"]["id"]
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE provider_track_actions SET action='ignored' WHERE provider_id=? AND external_id=?",
                (PROVIDER, "401"),
            )
        task = service.run_task(task_id)
        self.assertEqual(task.status, DownloadStatus.SKIPPED)
        self.assertFalse((self.music / "MusicArk").exists())

    def test_running_recovery_is_retryable_failure(self) -> None:
        task = DownloadTask(
            task_type="provider_download",
            source_id="99",
            provider_id=DOWNLOAD_PROVIDER,
            target_folder=str(self.music),
            status=DownloadStatus.RUNNING,
        )
        repo = DownloadStorageRepository(self.db)
        repo.upsert_task(task)
        self.assertEqual(repo.recover_interrupted(), 1)
        recovered = repo.get_task(task.id)
        self.assertEqual(recovered.status, DownloadStatus.FAILED)
        self.assertEqual(recovered.error_code, "interrupted")

    def test_sensitive_payload_is_never_persisted(self) -> None:
        task = DownloadTask(
            task_type="provider_download",
            source_id="1",
            provider_id=DOWNLOAD_PROVIDER,
            target_folder=str(self.music),
            raw_payload={"track_id": "1", "token": "secret"},
        )
        with self.assertRaises(Exception):
            DownloadStorageRepository(self.db).upsert_task(task)

    def test_filename_is_windows_safe_and_stable(self) -> None:
        name = yandex_download_filename(["A/B:C*D?E\"F<G>H|I"], "CON. ", "123456")
        self.assertIn("yandex_123456", name)
        self.assertFalse(any(char in name for char in '<>:"/\\|?*'))
        self.assertEqual(Path(name).name, name)
        self.assertEqual(sanitize_filename("CON.mp3"), "_CON.mp3")


class DownloadMigrationV07Tests(unittest.TestCase):
    def test_v16_row_is_preserved_and_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy.db"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE app_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.execute("INSERT INTO app_metadata VALUES('schema_version','1.6.0')")
                conn.execute(
                    """
                    CREATE TABLE download_tasks(
                        id TEXT PRIMARY KEY, task_type TEXT NOT NULL, source_id TEXT NOT NULL,
                        provider_id TEXT NOT NULL, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
                        target_folder TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT,
                        finished_at TEXT, error_message TEXT, result_local_file_id INTEGER,
                        raw_payload_json TEXT
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO download_tasks(id,task_type,source_id,provider_id,status,target_folder,created_at) VALUES('old','x','7','p','failed','C:/Music','now')"
                )
                self.assertEqual(migrate_download_v07(conn), "1.7.0")
                self.assertEqual(migrate_download_v07(conn), "1.7.0")
                columns = {row[1] for row in conn.execute("PRAGMA table_info(download_tasks)")}
                self.assertTrue({"downloaded_bytes", "total_bytes", "cancel_requested", "target_root_id", "error_code", "updated_at"}.issubset(columns))
                self.assertEqual(conn.execute("SELECT source_id,status FROM download_tasks WHERE id='old'").fetchone(), ("7", "failed"))
                self.assertEqual(conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0], "1.7.0")


class YandexStreamingV07Tests(unittest.TestCase):
    class _Response:
        def __init__(self, chunks: list[bytes], length: str | None) -> None:
            self._chunks = chunks
            self.headers = {} if length is None else {"Content-Length": length}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
            del chunk_size
            yield from self._chunks

    def test_known_and_unknown_content_length_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = YandexMusicDownloadProvider(token="not-used")
            destination = Path(tmp) / "track.mp3"
            known: list[tuple[int, int | None]] = []
            with patch("musicark.download.provider.requests.get", return_value=self._Response([b"abc", b"def"], "6")):
                provider._download_to_file("temporary-url", destination, progress=lambda d, t: known.append((d, t)))
            self.assertEqual(known[-1], (6, 6))
            self.assertEqual(destination.read_bytes(), b"abcdef")

            destination.unlink()
            unknown: list[tuple[int, int | None]] = []
            with patch("musicark.download.provider.requests.get", return_value=self._Response([b"abc"], None)):
                provider._download_to_file("temporary-url", destination, progress=lambda d, t: unknown.append((d, t)))
            self.assertEqual(unknown[-1], (3, None))

    def test_cancel_cleans_part_and_never_promotes_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = YandexMusicDownloadProvider(token="not-used")
            destination = Path(tmp) / "track.mp3"
            calls = 0

            def cancelled() -> bool:
                nonlocal calls
                calls += 1
                return calls >= 2

            with patch("musicark.download.provider.requests.get", return_value=self._Response([b"abc", b"def"], "6")):
                with self.assertRaises(DownloadCancelledError):
                    provider._download_to_file("temporary-url", destination, cancelled=cancelled)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name(destination.name + ".part").exists())


if __name__ == "__main__":
    unittest.main()
