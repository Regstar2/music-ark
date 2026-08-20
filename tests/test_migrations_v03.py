"""Regression tests for upgrading a real v0.2 collection cache through current schema."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import initialize_database


class V03MigrationTests(unittest.TestCase):
    def test_v02_cache_upgrade_is_forward_only_idempotent_and_preserves_liked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".musicark" / "musicark.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute("CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    conn.execute("INSERT INTO app_metadata(key, value) VALUES ('schema_version', '1.1.1')")
                    conn.execute("""CREATE TABLE provider_collection_snapshots (provider_id TEXT NOT NULL, collection_id TEXT NOT NULL, account_json TEXT NOT NULL DEFAULT '{}', item_count INTEGER NOT NULL DEFAULT 0, refreshed_at TEXT NOT NULL, PRIMARY KEY(provider_id, collection_id))""")
                    conn.execute("""CREATE TABLE provider_collection_items (provider_id TEXT NOT NULL, collection_id TEXT NOT NULL, external_id TEXT NOT NULL, position INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(provider_id, collection_id, external_id))""")
                    account = json.dumps({"displayName": "Tester"})
                    track = json.dumps({"external_id": "101", "title": "Existing Like"})
                    conn.execute("INSERT INTO provider_collection_snapshots(provider_id, collection_id, account_json, item_count, refreshed_at) VALUES ('yandex_music', 'liked', ?, 1, '2026-08-11T10:00:00+00:00')", (account,))
                    conn.execute("INSERT INTO provider_collection_items(provider_id, collection_id, external_id, position, payload_json) VALUES ('yandex_music', 'liked', '101', 0, ?)", (track,))

            initialize_database(db_path)
            initialize_database(db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
                row = conn.execute("SELECT account_json, item_count, refreshed_at, collection_type, content_refreshed_at FROM provider_collection_snapshots WHERE provider_id='yandex_music' AND collection_id='liked'").fetchone()
                item = conn.execute("SELECT external_id, position, payload_json FROM provider_collection_items WHERE provider_id='yandex_music' AND collection_id='liked'").fetchone()
                columns = {r[1] for r in conn.execute("PRAGMA table_info(provider_collection_snapshots)")}
                local_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

            self.assertEqual(version, "1.9.0")
            self.assertEqual(json.loads(row[0])["displayName"], "Tester")
            self.assertEqual(row[1], 1)
            self.assertEqual(row[2], "2026-08-11T10:00:00+00:00")
            self.assertEqual(row[3], "liked")
            self.assertEqual(row[4], row[2])
            self.assertEqual(item[0:2], ("101", 0))
            self.assertEqual(json.loads(item[2])["title"], "Existing Like")
            self.assertTrue({"collection_type", "external_id", "title", "owner_name", "metadata_json", "source_position", "active", "content_refreshed_at"}.issubset(columns))
            self.assertIn("local_library_roots", local_tables)
            self.assertIn("matching_results", local_tables)
            self.assertIn("track_variant_results", local_tables)
            self.assertIn("provider_track_actions", local_tables)
            self.assertIn("download_settings", local_tables)
            self.assertIn("local_track_content_labels", local_tables)
            self.assertIn("provider_track_content_labels", local_tables)
            self.assertIn("variant_user_acceptance", local_tables)


if __name__ == "__main__":
    unittest.main()
