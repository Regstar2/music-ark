"""Tests for SQLite initialization and audit writing."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_required_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
            for table in (
                "app_metadata", "audit_log", "providers", "track_sources", "provider_tracks",
                "provider_playlists", "provider_raw_responses", "local_audio_files",
                "download_tasks", "tracks", "track_links", "match_conflicts",
                "matching_results", "track_variant_results", "provider_track_actions",
                "sync_plans", "sync_operations",
            ):
                self.assertIn(table, tables)

    def test_audit_log_insert_persists_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            repository = AuditLogRepository(db_path)
            repository.append(AuditEvent(event_type="db_init", entity_type="database", entity_id="main", status="success", details="Initialized from unit test."))
            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute("SELECT event_type, entity_type, entity_id, status FROM audit_log;").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ("db_init", "database", "main", "success"))


if __name__ == "__main__":
    unittest.main()
