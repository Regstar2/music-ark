"""Tests for desktop platform bridge snapshot and actions."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.core.errors import MetadataEditorError
from musicark.platform_bridge import build_snapshot, run_action, update_settings
from musicark.storage.database import initialize_database


class PlatformBridgeTests(unittest.TestCase):
    def test_snapshot_contains_expected_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            snapshot = build_snapshot(base_dir=base_dir)
            self.assertIn("dashboard", snapshot)
            self.assertIn("collection", snapshot)
            self.assertIn("local_library", snapshot)
            self.assertIn("download_queue", snapshot)
            self.assertIn("sync_plans", snapshot)
            self.assertIn("logs", snapshot)
            self.assertIn("settings", snapshot)
            self.assertIn("mvp_hints", snapshot)
            mh = snapshot["mvp_hints"]
            self.assertIn("schema_version", mh)
            self.assertEqual(mh["schema_version"], "1.4.0")
            self.assertIn("latest_sync_plan_id", mh)

    def test_sync_execute_safe_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            with self.assertRaises(ValueError):
                run_action("sync_execute_safe", base_dir=base_dir, payload={"confirm": False})

    def test_download_enqueue_run_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            with self.assertRaises(ValueError):
                run_action(
                    "download_enqueue_run",
                    base_dir=base_dir,
                    payload={"external_id": "1"},
                )

    def test_sync_plan_action_returns_plan_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            result = run_action("sync_plan", base_dir=base_dir)
            self.assertIn("id", result)
            self.assertIn("summary", result)
            self.assertIn("operations_count", result)

    def test_metadata_get_requires_payload_local_file_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            with self.assertRaises(ValueError):
                run_action("metadata_get", base_dir=base_dir, payload={})

    def test_metadata_get_missing_on_disk_reports_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp)
            db_path = base_dir / ".musicark" / "musicark.db"
            initialize_database(db_path)
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO local_audio_files(
                        path, sha256, file_size, duration_seconds, codec, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(base_dir / "missing.mp3"), "a" * 64, 1, 0.0, "mp3", "{}"),
                )
                conn.commit()
            with self.assertRaises(MetadataEditorError):
                run_action("metadata_get", base_dir=base_dir, payload={"local_file_id": 1})

    def test_update_settings_persists_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            result = update_settings(
                base_dir=base_dir,
                database_path=".musicark/custom.db",
                log_level="DEBUG",
            )
            self.assertEqual(result["settings"]["database_path"], ".musicark/custom.db")
            self.assertEqual(result["settings"]["log_level"], "DEBUG")


if __name__ == "__main__":
    unittest.main()
