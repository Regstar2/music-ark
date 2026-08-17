"""SQLite forward migrations used by the restarted desktop app."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import initialize_database


class StableDesktopMigrationsTests(unittest.TestCase):
    def test_db_init_sets_schema_version_and_persistent_cache_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db_path)
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
                self.assertEqual(row[0], "1.8.4")
                idx_rows = conn.execute("PRAGMA index_list(audit_log)").fetchall()
                self.assertIn("idx_audit_log_created_at", {r[1] for r in idx_rows})
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                self.assertIn("provider_collection_snapshots", tables)
                self.assertIn("provider_collection_items", tables)
                self.assertIn("local_library_roots", tables)
                self.assertIn("matching_results", tables)
                self.assertIn("track_variant_results", tables)
                self.assertIn("provider_track_actions", tables)
                self.assertIn("download_settings", tables)
                self.assertIn("local_track_content_labels", tables)
                self.assertIn("provider_track_content_labels", tables)
                self.assertIn("variant_user_acceptance", tables)

    def test_repair_migration_replaces_incompatible_experimental_cache_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute("DROP TABLE provider_collection_items")
                    conn.execute("DROP TABLE provider_collection_snapshots")
                    conn.execute("CREATE TABLE provider_collection_items (external_id TEXT PRIMARY KEY, payload TEXT)")
                    conn.execute("CREATE TABLE provider_collection_snapshots (provider TEXT PRIMARY KEY, payload TEXT)")
                    conn.execute("UPDATE app_metadata SET value='1.1.0' WHERE key='schema_version'")
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
                item_columns = {row[1] for row in conn.execute("PRAGMA table_info(provider_collection_items)")}
                snapshot_columns = {row[1] for row in conn.execute("PRAGMA table_info(provider_collection_snapshots)")}
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertEqual(version, "1.8.4")
            self.assertTrue({"provider_id", "collection_id", "external_id", "position", "payload_json"}.issubset(item_columns))
            self.assertTrue({"provider_id", "collection_id", "account_json", "item_count", "refreshed_at", "collection_type", "metadata_json"}.issubset(snapshot_columns))
            self.assertIn("track_variant_results", tables)
            self.assertIn("provider_track_actions", tables)
            self.assertIn("download_settings", tables)
            self.assertIn("local_track_content_labels", tables)
            self.assertIn("provider_track_content_labels", tables)
            self.assertIn("variant_user_acceptance", tables)


if __name__ == "__main__":
    unittest.main()
