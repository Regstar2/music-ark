"""Tests for SQLite initialization and audit writing."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from musicark.core.errors import StorageError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_required_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table';"
                    ).fetchall()
                }
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()[0]

            self.assertEqual(version, "1.9.0")
            self.assertIn("app_metadata", tables)
            self.assertIn("audit_log", tables)
            self.assertIn("providers", tables)
            self.assertIn("track_sources", tables)
            self.assertIn("provider_tracks", tables)
            self.assertIn("provider_playlists", tables)
            self.assertIn("provider_raw_responses", tables)
            self.assertIn("local_audio_files", tables)
            self.assertIn("download_tasks", tables)
            self.assertIn("download_settings", tables)
            self.assertIn("tracks", tables)
            self.assertIn("track_links", tables)
            self.assertIn("match_conflicts", tables)
            self.assertIn("matching_results", tables)
            self.assertIn("track_variant_results", tables)
            self.assertIn("provider_track_actions", tables)
            self.assertIn("sync_plans", tables)
            self.assertIn("sync_operations", tables)
            self.assertIn("local_track_content_labels", tables)
            self.assertIn("provider_track_content_labels", tables)
            self.assertIn("variant_user_acceptance", tables)
            self.assertIn("managed_yandex_playlists", tables)
            self.assertIn("yandex_upload_mappings", tables)
            self.assertIn("provider_track_availability_history", tables)
            self.assertIn("yandex_upload_batches", tables)
            self.assertIn("yandex_upload_batch_items", tables)

    def test_initialize_database_retries_one_transient_locked_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            real_connect = sqlite3.connect
            attempts = 0

            def flaky_connect(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise sqlite3.OperationalError("database is locked")
                return real_connect(*args, **kwargs)

            with (
                patch(
                    "musicark.storage.database.sqlite3.connect",
                    side_effect=flaky_connect,
                ),
                patch("musicark.storage.database.time.sleep") as sleep,
            ):
                initialize_database(db_path)

            self.assertEqual(attempts, 2)
            sleep.assert_called_once()
            with closing(sqlite3.connect(db_path)) as conn:
                version = conn.execute(
                    "SELECT value FROM app_metadata WHERE key='schema_version'"
                ).fetchone()[0]
            self.assertEqual(version, "1.9.0")

    def test_initialize_database_does_not_retry_non_locking_sqlite_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            with (
                patch(
                    "musicark.storage.database.sqlite3.connect",
                    side_effect=sqlite3.OperationalError("disk I/O error"),
                ) as connect,
                patch("musicark.storage.database.time.sleep") as sleep,
            ):
                with self.assertRaises(StorageError):
                    initialize_database(db_path)

            self.assertEqual(connect.call_count, 1)
            sleep.assert_not_called()

    def test_audit_log_insert_persists_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            repository = AuditLogRepository(db_path)

            repository.append(
                AuditEvent(
                    event_type="db_init",
                    entity_type="database",
                    entity_id="main",
                    status="success",
                    details="Initialized from unit test.",
                )
            )

            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "SELECT event_type, entity_type, entity_id, status FROM audit_log;"
                ).fetchall()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ("db_init", "database", "main", "success"))


if __name__ == "__main__":
    unittest.main()
