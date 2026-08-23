"""v1.0 release-blocker regressions for matching responsiveness."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.matching.responsive_candidates import ResponsiveCandidateGenerator
from musicark.matching.responsive_service import ResponsiveMatchingService
from musicark.providers.models import ProviderTrack
from musicark.storage.database import initialize_database
from musicark.storage.provider_storage import ProviderStorageRepository


class MatchingResponsivenessV100Tests(unittest.TestCase):
    def test_large_run_reports_monotonic_progress_to_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            providers = ProviderStorageRepository(db)
            for index in range(60):
                providers.upsert_provider_track(
                    ProviderTrack(
                        "yandex_music",
                        str(index + 1),
                        f"Missing {index}",
                        (f"Artist {index}",),
                        duration_seconds=180 + index,
                    )
                )

            updates: list[tuple[int, int]] = []
            result = ResponsiveMatchingService(database_path=db).run(
                progress=lambda processed, total: updates.append((processed, total))
            )

            self.assertEqual(result["total"], 60)
            self.assertGreaterEqual(len(updates), 4)
            self.assertEqual(updates[0], (0, 60))
            self.assertEqual(updates[-1], (60, 60))
            self.assertEqual([item[0] for item in updates], sorted(item[0] for item in updates))
            self.assertTrue(all(item[1] == 60 for item in updates))

    def test_exact_yandex_filename_index_is_built_once_per_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO local_audio_files(
                            id, path, normalized_path, file_name, extension, sha256,
                            file_size, duration_seconds, codec, metadata_json, title,
                            artists_json, album, availability, normalized_title,
                            normalized_artists_text, duration_bucket
                        ) VALUES (?, ?, ?, ?, '.mp3', '', 1000, 180, 'mp3', ?, ?, ?,
                                  'Album', 'available', ?, ?, 36)
                        """,
                        [
                            (
                                index,
                                f"/music/yandex_{index}.mp3",
                                f"/music/yandex_{index}.mp3",
                                f"yandex_{index}.mp3",
                                json.dumps({"title": f"Song {index}", "artists": ["Artist"]}),
                                f"Song {index}",
                                json.dumps(["Artist"]),
                                f"song {index}",
                                "artist",
                            )
                            for index in range(1, 31)
                        ],
                    )

                statements: list[str] = []
                conn.set_trace_callback(statements.append)
                generator = ResponsiveCandidateGenerator(conn)
                for index in range(1, 31):
                    candidates = generator.generate(
                        {
                            "provider_id": "yandex_music",
                            "external_id": str(index),
                            "payload": {
                                "title": f"Song {index}",
                                "artists": ["Artist"],
                                "duration_seconds": 180,
                            },
                        }
                    )
                    self.assertTrue(candidates)
                    self.assertEqual(int(candidates[0]["id"]), index)

                exact_preload_queries = [
                    statement
                    for statement in statements
                    if "source_provider_id='yandex_music'" in statement
                    and "FROM local_audio_files" in statement
                ]
                self.assertEqual(len(exact_preload_queries), 1)


if __name__ == "__main__":
    unittest.main()
