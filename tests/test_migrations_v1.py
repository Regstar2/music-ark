"""SQLite forward migrations for v1.0 stable desktop MVP."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import initialize_database


class StableDesktopMigrationsTests(unittest.TestCase):
    def test_db_init_sets_schema_version_and_audit_index_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db_path)
            initialize_database(db_path)
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'",
                ).fetchone()
                self.assertEqual(row[0], "1.0.0")
                idx_rows = conn.execute("PRAGMA index_list(audit_log)").fetchall()
                names = {r[1] for r in idx_rows}
                self.assertIn("idx_audit_log_created_at", names)


if __name__ == "__main__":
    unittest.main()
