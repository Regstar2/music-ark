"""SQLite forward migrations used by the restarted desktop app."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import initialize_database


class StableDesktopMigrationsTests(unittest.TestCase):
    def test_db_init_sets_schema_version_and_persistent_cache_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db_path)
            initialize_database(db_path)
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'",
                ).fetchone()
                self.assertEqual(row[0], "1.1.0")

                idx_rows = conn.execute("PRAGMA index_list(audit_log)").fetchall()
                self.assertIn("idx_audit_log_created_at", {r[1] for r in idx_rows})

                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("provider_collection_snapshots", tables)
                self.assertIn("provider_collection_items", tables)


if __name__ == "__main__":
    unittest.main()
