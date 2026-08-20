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
        initialize_database(self.db)

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
            if "settings" in args:
                return subprocess.CompletedProcess(args, 0, "(user set) Mode: TunnelOnly", "")
            return subprocess.CompletedProcess(args, 0, "Status update: Connected", "")

        service = WarpService(self.db, runner=runner)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", return_value=False):
            status = service.status()
        self.assertEqual(status.state, WarpState.CONNECTED)
        self.assertEqual(status.service_mode, "TunnelOnly")
        self.assertIn("2026.6.905.0", status.version)

    def test_proxy_ready_takes_precedence_over_human_cli_output(self) -> None:
        def runner(args, **kwargs):
            if "settings" in args:
                return subprocess.CompletedProcess(args, 0, "Mode: WarpProxy", "")
            return subprocess.CompletedProcess(args, 0, "unknown localized text", "")

        service = WarpService(self.db, runner=runner)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", return_value=True):
            self.assertEqual(service.status().state, WarpState.PROXY_READY)

    def test_connect_switches_already_connected_client_to_proxy_without_redundant_connect(self) -> None:
        calls = []
        proxy_checks = iter([False, True])

        def runner(args, **kwargs):
            calls.append(args)
            if args[-2:] == ["mode", "--help"]:
                return subprocess.CompletedProcess(args, 0, "Possible values: warp proxy tunnel_only", "")
            if args[-2:] == ["mode", "proxy"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[-1:] == ["--version"]:
                return subprocess.CompletedProcess(args, 0, "warp-cli 2026.6.905.0", "")
            if args[-1:] == ["settings"]:
                return subprocess.CompletedProcess(args, 0, "(user set) Mode: WarpProxy", "")
            if args[-1:] == ["status"]:
                return subprocess.CompletedProcess(args, 0, "Status update: Connected", "")
            return subprocess.CompletedProcess(args, 1, "", "unexpected")

        service = WarpService(self.db, runner=runner, sleeper=lambda _: None)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", side_effect=lambda: next(proxy_checks, True)):
            status = service.connect()
        self.assertEqual(status.state, WarpState.PROXY_READY)
        self.assertTrue(any(call[-2:] == ["mode", "proxy"] for call in calls))
        self.assertFalse(any(call[-1:] == ["connect"] for call in calls))

    def test_connect_calls_connect_when_proxy_mode_switch_leaves_client_disconnected(self) -> None:
        calls = []
        connected = False

        def runner(args, **kwargs):
            nonlocal connected
            calls.append(args)
            if args[-2:] == ["mode", "--help"]:
                return subprocess.CompletedProcess(args, 0, "Possible values: warp proxy tunnel_only", "")
            if args[-2:] == ["mode", "proxy"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[-1:] == ["connect"]:
                connected = True
                return subprocess.CompletedProcess(args, 0, "Success", "")
            if args[-1:] == ["--version"]:
                return subprocess.CompletedProcess(args, 0, "warp-cli test", "")
            if args[-1:] == ["settings"]:
                return subprocess.CompletedProcess(args, 0, "Mode: WarpProxy", "")
            if args[-1:] == ["status"]:
                return subprocess.CompletedProcess(args, 0, "Status update: Connected" if connected else "Status update: Disconnected", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        service = WarpService(self.db, runner=runner, sleeper=lambda _: None)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", side_effect=lambda: connected):
            status = service.connect()
        self.assertEqual(status.state, WarpState.PROXY_READY)
        proxy_index = next(i for i, call in enumerate(calls) if call[-2:] == ["mode", "proxy"])
        connect_index = next(i for i, call in enumerate(calls) if call[-1:] == ["connect"])
        self.assertLess(proxy_index, connect_index)

    def test_connect_fails_closed_if_proxy_mode_is_not_exposed(self) -> None:
        def runner(args, **kwargs):
            if args[-2:] == ["mode", "--help"]:
                return subprocess.CompletedProcess(args, 0, "Possible values: warp tunnel_only", "")
            if args[-1:] == ["--version"]:
                return subprocess.CompletedProcess(args, 0, "warp-cli test", "")
            if args[-1:] == ["settings"]:
                return subprocess.CompletedProcess(args, 0, "Mode: TunnelOnly", "")
            if args[-1:] == ["status"]:
                return subprocess.CompletedProcess(args, 0, "Status update: Connected", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        service = WarpService(self.db, runner=runner, sleeper=lambda _: None)
        with patch.object(service, "_cli", return_value="warp-cli"), patch.object(service, "_proxy_ready", return_value=False):
            status = service.connect()
        self.assertEqual(status.state, WarpState.UNSUPPORTED_VERSION)

    def test_ownership_marker_is_explicit(self) -> None:
        service = WarpService(self.db)
        service._mark_owned("test")  # noqa: SLF001 - verifies persisted uninstaller boundary.
        with sqlite3.connect(self.db) as conn:
            row = conn.execute("SELECT installed_by_musicark FROM network_component_state WHERE component_id='cloudflare_warp'").fetchone()
        self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
