"""Tests for desktop platform bridge snapshot and actions."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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

    def test_sync_plan_action_returns_plan_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            initialize_database(base_dir / ".musicark" / "musicark.db")
            result = run_action("sync_plan", base_dir=base_dir)
            self.assertIn("id", result)
            self.assertIn("summary", result)
            self.assertIn("operations_count", result)

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
