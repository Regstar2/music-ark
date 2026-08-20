"""v0.4 -> current forward migration coverage, including preserved v0.5 state."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import SCHEMA_STATEMENTS, initialize_database
from musicark.storage.migrations import MIGRATION_STEPS


class MatchingMigrationV05Tests(unittest.TestCase):
    def test_v04_database_migrates_forward_without_losing_cached_or_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    for statement in SCHEMA_STATEMENTS:
                        conn.execute(statement)
                    conn.execute(
                        "INSERT INTO app_metadata(key, value) VALUES('schema_version', '0.1.0')"
                    )
                    for version, steps in MIGRATION_STEPS:
                        if version > "1.3.0":
                            continue
                        for step in steps:
                            step(conn)
                        conn.execute(
                            """
                            INSERT INTO app_metadata(key, value) VALUES('schema_version', ?)
                            ON CONFLICT(key) DO UPDATE SET value=excluded.value
                            """,
                            (version,),
                        )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at
                        ) VALUES ('yandex_music', 'liked', '{"user":"kept"}', 1, '2026-08-14T00:00:00Z')
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_items(
                            provider_id, collection_id, external_id, position, payload_json
                        ) VALUES ('yandex_music', 'liked', '101', 0,
                                  '{"external_id":"101","title":"Song","artists":["Artist"]}')
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO local_library_roots(path, normalized_path)
                        VALUES ('C:/Music', 'c:/music')
                        """
                    )
                    root_id = int(conn.execute("SELECT id FROM local_library_roots").fetchone()[0])
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            library_root_id, path, normalized_path, file_name, extension,
                            sha256, file_size, modified_ns, duration_seconds, codec,
                            metadata_json, title, artists_json, album, availability
                        ) VALUES (?, 'C:/Music/Song.flac', 'c:/music/song.flac', 'Song.flac',
                                  '.flac', '', 1234, 1, 200, 'flac',
                                  '{"title":"Song","artists":["Artist"]}', 'Song',
                                  '["Artist"]', 'Album', 'available')
                        """,
                        (root_id,),
                    )

            initialize_database(db)
            initialize_database(db)

            with closing(sqlite3.connect(db)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()[0]
                cache_count = conn.execute(
                    "SELECT COUNT(*) FROM provider_collection_items WHERE external_id='101'"
                ).fetchone()[0]
                local = conn.execute(
                    """
                    SELECT title, artists_json, normalized_title, normalized_artists_text,
                           duration_bucket
                    FROM local_audio_files WHERE path='C:/Music/Song.flac'
                    """
                ).fetchone()
                result_table = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='matching_results'"
                ).fetchone()
                variant_table = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='track_variant_results'"
                ).fetchone()
                coverage_table = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='provider_track_actions'"
                ).fetchone()
                download_settings = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='download_settings'"
                ).fetchone()

            self.assertEqual(version, "1.9.0")
            self.assertEqual(cache_count, 1)
            self.assertEqual(local[0], "Song")
            self.assertEqual(local[1], '["Artist"]')
            self.assertEqual(local[2], "song")
            self.assertEqual(local[3], "artist")
            self.assertEqual(local[4], 40)
            self.assertIsNotNone(result_table)
            self.assertIsNotNone(variant_table)
            self.assertIsNotNone(coverage_table)
            self.assertIsNotNone(download_settings)


if __name__ == "__main__":
    unittest.main()
