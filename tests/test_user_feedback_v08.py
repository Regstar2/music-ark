from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.coverage.repository import CoverageRepository
from musicark.download import bridge as download_bridge
from musicark.download.models import DownloadStatus, DownloadTask
from musicark.download.service import DownloadService
from musicark.matching.scope import MatchingScopeState
from musicark.matching.service import MatchingService
from musicark.storage.database import initialize_database
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


PROVIDER = "yandex_music"


def _snapshot(
    db: Path,
    collection_id: str,
    *,
    collection_type: str,
    external_id: str | None,
    title: str,
    tracks: list[tuple[str, str, str]],
) -> None:
    with closing(sqlite3.connect(db)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO provider_collection_snapshots(
                    provider_id, collection_id, account_json, item_count, refreshed_at,
                    collection_type, external_id, title, metadata_json, source_position, active
                ) VALUES (?, ?, '{}', ?, datetime('now'), ?, ?, ?, '{}', 0, 1)
                """,
                (
                    PROVIDER,
                    collection_id,
                    len(tracks),
                    collection_type,
                    external_id,
                    title,
                ),
            )
            for position, (track_id, track_title, artist) in enumerate(tracks):
                payload = {
                    "provider_id": PROVIDER,
                    "external_id": track_id,
                    "title": track_title,
                    "artists": [artist],
                    "album_title": "Album",
                    "duration_seconds": 180.0,
                    "availability": "available",
                }
                conn.execute(
                    """
                    INSERT INTO provider_collection_items(
                        provider_id, collection_id, external_id, position, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        PROVIDER,
                        collection_id,
                        track_id,
                        position,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )


class UserFeedbackV08Tests(unittest.TestCase):
    def test_matching_runs_only_last_opened_playlist_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            _snapshot(
                db,
                "liked",
                collection_type="liked",
                external_id=None,
                title="Мне нравится",
                tracks=[
                    ("1", "Liked only", "Artist"),
                    ("2", "Playlist A", "Artist"),
                    ("3", "Playlist B", "Artist"),
                    ("4", "Playlist C", "Artist"),
                ],
            )
            _snapshot(
                db,
                "playlist:test",
                collection_type="playlist",
                external_id="test",
                title="ТЕСТ",
                tracks=[
                    ("2", "Playlist A", "Artist"),
                    ("3", "Playlist B", "Artist"),
                    ("4", "Playlist C", "Artist"),
                ],
            )
            MatchingScopeState(db).set_playlist("test")

            service = MatchingService(database_path=db)
            run = service.run()
            self.assertEqual(run["collectionId"], "playlist:test")
            self.assertEqual(run["providerIdentities"], 3)
            self.assertEqual(run["total"], 3)
            self.assertEqual(run["unmatched"], 3)

            summary = service.summary()
            self.assertEqual(summary["collectionId"], "playlist:test")
            self.assertEqual(summary["yandexTracks"], 3)
            self.assertEqual(summary["processed"], 3)

            results = service.results(limit=20)
            self.assertEqual(results["count"], 3)
            self.assertEqual(
                {item["externalId"] for item in results["items"]},
                {"2", "3", "4"},
            )

    def test_configured_empty_root_excludes_orphan_track_and_path_search_does_not_hide_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "musicark.db"
            initialize_database(db)
            _snapshot(
                db,
                "playlist:test",
                collection_type="playlist",
                external_id="test",
                title="ТЕСТ",
                tracks=[("69046542", "Ахегао", "Мэйби Бэйби")],
            )
            MatchingScopeState(db).set_playlist("test")

            # Simulate a historical/legacy indexed file that is not owned by any
            # configured Local Library root.
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            path, normalized_path, file_name, extension, sha256, file_size,
                            duration_seconds, codec, metadata_json, title, artists_json,
                            album, availability
                        ) VALUES (?, ?, ?, '.mp3', 'sha', 1000, 180, 'mp3', ?, ?, ?, ?, 'available')
                        """,
                        (
                            "C:/outside/ahegao.mp3",
                            "c:/outside/ahegao.mp3",
                            "ahegao.mp3",
                            json.dumps({"title": "Ахегао", "artists": ["Мэйби Бэйби"]}, ensure_ascii=False),
                            "Ахегао",
                            json.dumps(["Мэйби Бэйби"], ensure_ascii=False),
                            "Album",
                        ),
                    )

            service = MatchingService(database_path=db)
            first = service.run()
            self.assertEqual(first["matched"], 1, "legacy no-root compatibility should still see the row")

            empty_music = root / "empty-music"
            empty_music.mkdir()
            LocalLibraryStorageRepository(db).add_root(empty_music)

            second = service.run()
            self.assertEqual(second["invalidated"], 1)
            self.assertEqual(second["matched"], 0)
            self.assertEqual(second["unmatched"], 1)
            self.assertEqual(service.summary()["localTracks"], 0)

            coverage = CoverageRepository(db).get_track(
                provider_id=PROVIDER,
                external_id="69046542",
            )
            self.assertIsNotNone(coverage)
            self.assertEqual(coverage["coverageStatus"], "missing")

            # The Matching search field is not a Local Library path selector. If the
            # configured root itself was pasted there (including quotes), do not leave
            # the page permanently filtered to zero rows.
            listed = service.results(search=f'"{empty_music}"')
            self.assertEqual(listed["search"], "")
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["items"][0]["externalId"], "69046542")

    def test_downloads_default_view_is_operational_and_completed_history_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            repository = DownloadStorageRepository(db)

            for index in range(150):
                repository.upsert_task(
                    DownloadTask(
                        id=f"completed-{index:03d}",
                        task_type="provider_download",
                        source_id=str(index),
                        provider_id="yandex_music_download",
                        target_folder=str(Path(tmp) / "Music"),
                        status=DownloadStatus.COMPLETED,
                        finished_at=f"2026-08-16T00:{index // 60:02d}:{index % 60:02d}+00:00",
                        raw_payload={
                            "source_provider_id": "yandex_music",
                            "title": f"Track {index}",
                            "artists": ["Artist"],
                            "target_filename": f"track-{index}.mp3",
                        },
                    )
                )
            for task_id, status in (
                ("queued-current", DownloadStatus.QUEUED),
                ("failed-current", DownloadStatus.FAILED),
            ):
                repository.upsert_task(
                    DownloadTask(
                        id=task_id,
                        task_type="provider_download",
                        source_id=task_id,
                        provider_id="yandex_music_download",
                        target_folder=str(Path(tmp) / "Music"),
                        status=status,
                        raw_payload={
                            "source_provider_id": "yandex_music",
                            "title": task_id,
                            "artists": ["Artist"],
                        },
                    )
                )

            service = DownloadService(database_path=db)
            summary = download_bridge._user_summary(service)
            self.assertEqual(summary["counts"]["completed"], 100)

            default_view = download_bridge._user_tasks(service, status="", limit=5000)
            self.assertEqual(default_view["count"], 2)
            self.assertEqual(
                {item["status"] for item in default_view["items"]},
                {"queued", "failed"},
            )

            history = download_bridge._user_tasks(service, status="completed", limit=5000)
            self.assertEqual(history["count"], 100)
            self.assertEqual(
                len(repository.list_tasks(status="completed", limit=5000)),
                100,
            )


if __name__ == "__main__":
    unittest.main()
