"""v1.0 acceptance regressions for the resilient large-download worker (#51)."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from yandex_music.exceptions import UnauthorizedError

from musicark.download.bridge import _queued_user_task_ids
from musicark.download.models import DownloadTask
from musicark.download.provider import DownloadProviderError
from musicark.download.resilient_yandex import ResilientYandexMusicDownloadProvider
from musicark.download.worker_bridge import WorkerCircuit, _safe_request
from musicark.providers.yandex_music_provider import YandexAuthenticationError
from musicark.runtime_cli import _ENTRY_POINTS
from musicark.storage.database import initialize_database


class _QueueServiceStub:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path


class ResilientYandexWorkerTests(unittest.TestCase):
    def _task(self, external_id: str) -> DownloadTask:
        return DownloadTask(
            task_type="provider_download",
            source_id=external_id,
            provider_id="yandex_music_download",
            target_folder="C:/Music",
            raw_payload={"track_id": external_id},
        )

    def test_yandex_client_is_initialized_once_per_provider_worker(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        sentinel = object()
        with patch("yandex_music.Client") as client_type:
            client_type.return_value.init.return_value = sentinel
            first = provider._build_client()  # noqa: SLF001
            second = provider._build_client()  # noqa: SLF001

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        client_type.assert_called_once_with("fake-token")
        client_type.return_value.init.assert_called_once_with()

    def test_unauthorized_during_client_init_remains_authentication(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        with patch("yandex_music.Client") as client_type:
            client_type.return_value.init.side_effect = UnauthorizedError("init denied")
            with self.assertRaises(YandexAuthenticationError):
                provider._build_client()  # noqa: SLF001
        self.assertIsNone(provider._client)  # noqa: SLF001

    def test_unauthorized_during_normal_track_lookup_remains_authentication(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        client = Mock()
        client.tracks.side_effect = UnauthorizedError("track lookup denied")
        provider._client = client  # noqa: SLF001

        with self.assertRaises(YandexAuthenticationError):
            provider._resolve_track_and_link_once("69420846", "best")  # noqa: SLF001
        self.assertIsNone(provider._client)  # noqa: SLF001

    def test_download_info_unauthorized_is_per_track_provider_rejection(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        client = Mock()
        track = Mock()
        client.tracks.return_value = [track]
        track.get_download_info.side_effect = UnauthorizedError("download info denied")
        provider._client = client  # noqa: SLF001

        with self.assertRaises(DownloadProviderError) as caught:
            provider._resolve_track_and_link_once("69420846", "best")  # noqa: SLF001

        self.assertEqual(caught.exception.code, "provider_rejected")
        self.assertIs(provider._client, client)  # noqa: SLF001

    def test_direct_link_unauthorized_is_per_track_provider_rejection(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        client = Mock()
        track = Mock()
        info = Mock()
        client.tracks.return_value = [track]
        track.get_download_info.return_value = [info]
        info.get_direct_link.side_effect = UnauthorizedError("direct link denied")
        provider._client = client  # noqa: SLF001
        with patch.object(provider, "_select_download_info", return_value=info):
            with self.assertRaises(DownloadProviderError) as caught:
                provider._resolve_track_and_link_once("69420846", "best")  # noqa: SLF001

        self.assertEqual(caught.exception.code, "provider_rejected")
        self.assertIs(provider._client, client)  # noqa: SLF001

    def test_transient_failure_retries_with_bounded_exponential_backoff(self) -> None:
        sleeps: list[float] = []
        attempts = 0
        provider = ResilientYandexMusicDownloadProvider(
            token="fake-token",
            retry_attempts=3,
            sleeper=sleeps.append,
        )

        def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise DownloadProviderError("temporary", code="provider_network")
            return "ok"

        self.assertEqual(provider._retry(operation), "ok")  # noqa: SLF001
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_permanent_provider_rejection_is_not_retried(self) -> None:
        sleeps: list[float] = []
        provider = ResilientYandexMusicDownloadProvider(
            token="fake-token",
            retry_attempts=3,
            sleeper=sleeps.append,
        )
        with self.assertRaises(DownloadProviderError) as caught:
            provider._retry(  # noqa: SLF001
                lambda: (_ for _ in ()).throw(
                    DownloadProviderError("rejected", code="provider_rejected")
                )
            )
        self.assertEqual(caught.exception.code, "provider_rejected")
        self.assertEqual(sleeps, [])

    def test_user_uploaded_uuid_has_explicit_ugc_code_without_network(self) -> None:
        provider = ResilientYandexMusicDownloadProvider(token="fake-token")
        task = self._task("34193055-9007-4aec-a723-d4c38acbe40b")
        with self.assertRaises(DownloadProviderError) as caught:
            provider._validated_track_id(task)  # noqa: SLF001
        self.assertEqual(caught.exception.code, "ugc_unsupported")

    def test_authentication_pauses_immediately(self) -> None:
        circuit = WorkerCircuit()
        pause = circuit.observe(
            {"status": "failed", "errorCode": "authentication"}
        )
        self.assertIsNotNone(pause)
        self.assertEqual(pause["code"], "authentication")  # type: ignore[index]

    def test_three_consecutive_systemic_failures_pause_worker(self) -> None:
        circuit = WorkerCircuit(failure_limit=3)
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "provider_network"}))
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "provider_timeout"}))
        pause = circuit.observe({"status": "failed", "errorCode": "rate_limited"})
        self.assertIsNotNone(pause)
        self.assertEqual(pause["code"], "provider_paused")  # type: ignore[index]
        self.assertEqual(circuit.systemic_failure_streak, 3)

    def test_permanent_track_failure_does_not_trip_systemic_circuit(self) -> None:
        circuit = WorkerCircuit(failure_limit=3)
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "provider_network"}))
        self.assertEqual(circuit.systemic_failure_streak, 1)
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "provider_rejected"}))
        self.assertEqual(circuit.systemic_failure_streak, 0)
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "track_unavailable"}))
        self.assertEqual(circuit.systemic_failure_streak, 0)
        self.assertIsNone(circuit.observe({"status": "failed", "errorCode": "ugc_unsupported"}))
        self.assertEqual(circuit.systemic_failure_streak, 0)

    def test_worker_protocol_requires_only_task_id_and_never_accepts_secret_fields(self) -> None:
        task_id, error = _safe_request('{"taskId":"task-1"}')
        self.assertEqual(task_id, "task-1")
        self.assertIsNone(error)
        task_id, error = _safe_request('{"token":"secret"}')
        self.assertIsNone(task_id)
        self.assertEqual(error["error"]["code"], "invalid_request")  # type: ignore[index]

    def test_persisted_queue_drains_beyond_legacy_5000_boundary_in_bounded_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            now = datetime.now(UTC).isoformat()
            rows = [
                (
                    f"task-{index:05d}",
                    "provider_download",
                    str(index),
                    "yandex_music_download",
                    "queued",
                    0.0,
                    str(Path(tmp) / "downloads"),
                    now,
                    "{}",
                )
                for index in range(5_247)
            ]
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO download_tasks(
                            id, task_type, source_id, provider_id, status, progress,
                            target_folder, created_at, raw_payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )

            service = _QueueServiceStub(db)
            seen: list[str] = []
            while True:
                batch = _queued_user_task_ids(service, limit=500)  # type: ignore[arg-type]
                if not batch:
                    break
                self.assertLessEqual(len(batch), 500)
                seen.extend(batch)
                placeholders = ",".join("?" for _ in batch)
                with closing(sqlite3.connect(db)) as conn:
                    with conn:
                        conn.execute(
                            f"UPDATE download_tasks SET status='completed' WHERE id IN ({placeholders})",
                            batch,
                        )

            self.assertEqual(len(seen), 5_247)
            self.assertEqual(len(set(seen)), 5_247)

    def test_flutter_run_task_uses_persistent_worker_process_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "ui" / "musicark_ui" / "lib" / "download_bridge.dart").read_text(
            encoding="utf-8"
        )
        production = source.split("class FakeDownloadBridge", 1)[0]
        self.assertIn("_runPersistentTask(taskId)", production)
        self.assertIn("musicark.download.worker_bridge", production)
        self.assertNotIn("_run('run_task', taskId: taskId)", production)

    def test_frozen_runtime_whitelists_worker_and_batch_download_bridges(self) -> None:
        self.assertIn("musicark.download.worker_bridge", _ENTRY_POINTS)
        self.assertIn("musicark.download.actions_bridge", _ENTRY_POINTS)


if __name__ == "__main__":
    unittest.main()
