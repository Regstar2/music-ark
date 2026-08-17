from __future__ import annotations

from contextlib import closing
import sqlite3
from pathlib import Path
import tempfile
import unittest

from musicark.storage.database import initialize_database


class CoverageMigrationV06Tests(unittest.TestCase):
    def test_realistic_15_database_migrates_to_current_without_data_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db)

            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.execute("DROP TABLE provider_track_actions")
                    conn.execute(
                        "UPDATE app_metadata SET value='1.5.0' WHERE key='schema_version'"
                    )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count,
                            refreshed_at, collection_type, active
                        ) VALUES ('yandex_music','liked','{"uid":"cached"}',1,
                                  datetime('now'),'liked',1)
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_items(
                            provider_id, collection_id, external_id, position, payload_json
                        ) VALUES ('yandex_music','liked','1',0,
                                  '{"external_id":"1","title":"Cached"}')
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            path, sha256, file_size, codec, title, artists_json,
                            availability
                        ) VALUES ('C:/Music/one.flac','sha',10,'flac','One',
                                  '["Artist"]','available')
                        """
                    )
                    local_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                    conn.execute(
                        """
                        INSERT INTO matching_results(
                            provider_id, external_id, status, local_file_id, confidence,
                            method, reason, matcher_version, provider_fingerprint,
                            local_fingerprint, manual
                        ) VALUES ('yandex_music','1','matched',?,1,'manual',
                                  'manual_accept',1,'provider-fp','local-fp',1)
                        """,
                        (local_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id,
                            local_file_id, confidence, match_method
                        ) VALUES (1,'yandex_music','1',?,1,'manual')
                        """,
                        (local_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO match_conflicts(
                            source_provider_id, source_external_id, local_file_id,
                            confidence, reason, status, score_breakdown_json,
                            candidate_rank, matcher_version
                        ) VALUES ('yandex_music','conflict',?,.8,'manual_review',
                                  'rejected','{}',1,1)
                        """,
                        (local_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO track_variant_results(
                            provider_id, external_id, local_file_id, status
                        ) VALUES ('yandex_music','1',?,'different_version')
                        """,
                        (local_id,),
                    )

            initialize_database(db)

            with closing(sqlite3.connect(db)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()[0]
                self.assertEqual(version, "1.8.4")
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM provider_collection_items"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM local_audio_files").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM matching_results").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM track_links").fetchone()[0], 1
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM match_conflicts").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM track_variant_results"
                    ).fetchone()[0],
                    1,
                )
                columns = {
                    row[1]
                    for row in conn.execute(
                        "PRAGMA table_info(provider_track_actions)"
                    ).fetchall()
                }
                self.assertTrue(
                    {"provider_id", "external_id", "action", "created_at", "updated_at"}
                    <= columns
                )
                download_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(download_tasks)").fetchall()
                }
                self.assertTrue(
                    {
                        "downloaded_bytes",
                        "total_bytes",
                        "cancel_requested",
                        "target_root_id",
                        "error_code",
                        "updated_at",
                    }
                    <= download_columns
                )
                sync_plan_columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(sync_plans)").fetchall()
                }
                self.assertTrue(
                    {
                        "planner_version",
                        "scope_type",
                        "scope_id",
                        "target_root_id",
                        "target_folder",
                        "input_fingerprint",
                        "applied_at",
                        "result_json",
                        "updated_at",
                    }
                    <= sync_plan_columns
                )
                current_tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("local_track_content_labels", current_tables)
                self.assertIn("provider_track_content_labels", current_tables)
                self.assertIn("variant_user_acceptance", current_tables)


if __name__ == "__main__":
    unittest.main()
