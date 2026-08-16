from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import wave

from musicark.coverage.repository import CoverageRepository
from musicark.download.models import DownloadTask
from musicark.download.provider import DownloadProvider
from musicark.download.service import DownloadService
from musicark.download.system import DownloadProviderRegistry
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.policy import MATCHER_VERSION
from musicark.providers.local_library import build_local_audio_file
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository


PROVIDER = "yandex_music"
DOWNLOAD_PROVIDER = "yandex_music_download"


class _Provider(DownloadProvider):
    @property
    def provider_id(self) -> str:
        return DOWNLOAD_PROVIDER

    def execute(self, task: DownloadTask):  # type: ignore[no-untyped-def]
        return self.execute_with_context(task)

    def execute_with_context(self, task, *, progress=None, cancelled=None):  # type: ignore[no-untyped-def]
        target = Path(task.target_folder)
        target.mkdir(parents=True, exist_ok=True)
        path = target / str(task.raw_payload["target_filename"])
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b"\x00\x00" * 8000)
        if progress is not None:
            progress(path.stat().st_size, path.stat().st_size)
        return build_local_audio_file(path)


class DownloadPreservesMissingTests(unittest.TestCase):
    def test_exact_download_does_not_make_other_missing_not_analyzed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root / ".musicark" / "musicark.db"
            target = root / "Music"
            target.mkdir()
            initialize_database(database)

            payloads = {
                "101": {
                    "provider_id": PROVIDER,
                    "external_id": "101",
                    "title": "Downloaded",
                    "artists": ["Artist"],
                    "album_title": "Album",
                    "duration_seconds": 1.0,
                },
                "202": {
                    "provider_id": PROVIDER,
                    "external_id": "202",
                    "title": "Still Missing",
                    "artists": ["Other Artist"],
                    "album_title": "Other Album",
                    "duration_seconds": 1.0,
                },
            }

            with closing(sqlite3.connect(database)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count,
                            refreshed_at, collection_type, title, metadata_json,
                            source_position, active
                        ) VALUES (?, 'liked', '{}', 2, datetime('now'), 'liked',
                                  'Мне нравится', '{}', 0, 1)
                        """,
                        (PROVIDER,),
                    )
                    for position, external_id in enumerate(("101", "202")):
                        payload = payloads[external_id]
                        conn.execute(
                            """
                            INSERT INTO provider_collection_items(
                                provider_id, collection_id, external_id, position, payload_json
                            ) VALUES (?, 'liked', ?, ?, ?)
                            """,
                            (PROVIDER, external_id, position, json.dumps(payload)),
                        )
                        conn.execute(
                            """
                            INSERT INTO provider_tracks(provider_id, external_id, payload_json)
                            VALUES (?, ?, ?)
                            """,
                            (PROVIDER, external_id, json.dumps(payload)),
                        )

            initial_fp = MatchingStorageRepository(database).local_library_fingerprint()
            with closing(sqlite3.connect(database)) as conn:
                with conn:
                    for external_id in ("101", "202"):
                        payload = payloads[external_id]
                        conn.execute(
                            """
                            INSERT INTO matching_results(
                                provider_id, external_id, status, local_file_id,
                                confidence, method, reason, matcher_version,
                                provider_fingerprint, local_fingerprint, manual
                            ) VALUES (?, ?, 'unmatched', NULL, 0, 'automatic',
                                      'no_candidates', ?, ?, ?, 0)
                            """,
                            (
                                PROVIDER,
                                external_id,
                                MATCHER_VERSION,
                                provider_fingerprint(PROVIDER, external_id, payload),
                                initial_fp,
                            ),
                        )
                    conn.execute(
                        """
                        INSERT INTO provider_track_actions(provider_id, external_id, action)
                        VALUES (?, '101', 'wanted')
                        """,
                        (PROVIDER,),
                    )

            registry = DownloadProviderRegistry()
            registry.register(_Provider())
            service = DownloadService(base_dir=root, registry=registry)
            service.set_target(str(target))

            before = CoverageRepository(database).summary(provider_id=PROVIDER)
            self.assertEqual(before["missing"], 2)
            self.assertEqual(before["notAnalyzed"], 0)

            task_id = service.enqueue("101")["task"]["id"]
            completed = service.run_task(task_id)
            self.assertEqual(completed.status.value, "completed")

            coverage = CoverageRepository(database)
            downloaded = coverage.get_track(provider_id=PROVIDER, external_id="101")
            untouched = coverage.get_track(provider_id=PROVIDER, external_id="202")
            after = coverage.summary(provider_id=PROVIDER)

            self.assertEqual(downloaded["coverageStatus"], "covered")
            self.assertEqual(untouched["coverageStatus"], "missing")
            self.assertEqual(after["covered"], 1)
            self.assertEqual(after["missing"], 1)
            self.assertEqual(after["notAnalyzed"], 0)


if __name__ == "__main__":
    unittest.main()
