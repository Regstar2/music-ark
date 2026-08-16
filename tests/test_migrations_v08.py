"""Schema 1.7.0 -> 1.8.0 migration preservation tests."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.coverage_migration import migrate_coverage_v06
from musicark.storage.database import SCHEMA_STATEMENTS, initialize_database
from musicark.storage.download_migration import migrate_download_v07
from musicark.storage.migrations import ensure_schema_version_seed, migrate_schema


class SyncMigrationV08Tests(unittest.TestCase):
    def test_realistic_v17_database_is_forward_migrated_and_legacy_sync_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    for statement in SCHEMA_STATEMENTS:
                        conn.execute(statement)
                    ensure_schema_version_seed(conn)
                    migrate_schema(conn)
                    migrate_coverage_v06(conn)
                    migrate_download_v07(conn)
                    conn.execute(
                        "INSERT INTO sync_plans(id, created_at, dry_run, summary_json, status) VALUES ('old', datetime('now'), 1, '{\"old\":1}', 'planned')"
                    )
                    conn.execute(
                        """
                        INSERT INTO sync_operations(
                            plan_id, operation_type, entity_id, reason, confidence,
                            is_dangerous, metadata_json
                        ) VALUES ('old', 'upload_candidate', 'x', 'legacy', 0.5, 1, '{}')
                        """
                    )
                    conn.execute(
                        "INSERT INTO provider_track_actions(provider_id, external_id, action) VALUES ('yandex_music','keep','wanted')"
                    )
            initialize_database(db)
            with closing(sqlite3.connect(db)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()[0]
                plan = conn.execute(
                    "SELECT planner_version, scope_type, status, summary_json FROM sync_plans WHERE id='old'"
                ).fetchone()
                op = conn.execute(
                    "SELECT operation_type, is_dangerous, status FROM sync_operations WHERE plan_id='old'"
                ).fetchone()
                action = conn.execute(
                    "SELECT action FROM provider_track_actions WHERE external_id='keep'"
                ).fetchone()[0]
            self.assertEqual(version, "1.8.0")
            self.assertEqual(plan, (0, "legacy", "planned", '{"old":1}'))
            self.assertEqual(op, ("upload_candidate", 1, "informational"))
            self.assertEqual(action, "wanted")


if __name__ == "__main__":
    unittest.main()
