from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from musicark.external_metadata.warp import WarpService, WarpState
from musicark.storage.database import initialize_database


class WarpV012Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "musicark.db"
        connection = initialize_database(self.db)
        connection.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_not_installed_is_reported_without_network_mutation(self) -> None:
        service = WarpService(self.db)
        with patch.object(service, "_cli", return_value=None):
            status = service.status()
        self.assertEqual(status.state, WarpState.NOT_INSTALLED)
        self.assertFalse(status.installed_by_musicark)

    def test_connected_cli_status_is_typed(self) -> None:
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if "--version" in args:
                return subprocess.CompletedProcess(args, 0, "warp-cli 2026.6.905.0", "")
            return subprocess.CompletedProcess(args, 0, "Status update: Connected", "")
        service = WarpService(self.db, runner=runner)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", return_value=False):
            status = service.status()
        self.assertEqual(status.state, WarpState.CONNECTED)
        self.assertIn("2026.6.905.0", status.version)

    def test_proxy_ready_takes_precedence_over_human_cli_output(self) -> None:
        def runner(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "unknown localized text", "")
        service = WarpService(self.db, runner=runner)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", return_value=True):
            self.assertEqual(service.status().state, WarpState.PROXY_READY)

    def test_ownership_marker_is_explicit(self) -> None:
        service = WarpService(self.db)
        service._mark_owned("test")  # noqa: SLF001 - verifies persisted uninstaller boundary.
        with sqlite3.connect(self.db) as conn:
            row = conn.execute("SELECT installed_by_musicark FROM network_component_state WHERE component_id='cloudflare_warp'").fetchone()
        self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
