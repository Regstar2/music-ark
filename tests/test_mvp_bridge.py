"""Tests for the persistent-library process bridge."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from musicark.mvp_bridge import bootstrap, cached, login, logout, refresh


class FakePersistentLibraryService:
    def bootstrap(self) -> dict:
        return {"session": {"hasStoredToken": True}, "library": {"source": "cache", "count": 1}}

    def login(self, token: str) -> dict:
        return {
            "session": {"hasStoredToken": True, "tokenEchoForTest": token},
            "library": {"source": "network", "count": 1},
        }

    def refresh(self) -> dict:
        return {"session": {"hasStoredToken": True}, "library": {"source": "network", "count": 2}}

    def cached(self) -> dict:
        return {"session": {"hasStoredToken": True}, "library": {"source": "cache", "count": 1}}

    def logout(self) -> dict:
        return {"session": {"hasStoredToken": False}, "library": {"source": "none", "count": 0}}


class MvpBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakePersistentLibraryService()

    def test_bridge_actions_delegate_to_persistent_service(self) -> None:
        self.assertEqual(bootstrap(self.service)["library"]["source"], "cache")
        self.assertEqual(login("secret", self.service)["session"]["tokenEchoForTest"], "secret")
        self.assertEqual(refresh(self.service)["library"]["count"], 2)
        self.assertEqual(cached(self.service)["library"]["source"], "cache")
        self.assertFalse(logout(self.service)["session"]["hasStoredToken"])

    def test_module_entrypoint_imports_cleanly_in_fresh_process(self) -> None:
        """Catch import-order cycles hidden by in-process unittest discovery."""
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("YANDEX_MUSIC_TOKEN", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "musicark.mvp_bridge",
                    "--base-dir",
                    str(Path(tmp)),
                    "login",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("circular import", result.stderr.lower())
        self.assertNotIn("ImportError", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "token_missing")


if __name__ == "__main__":
    unittest.main()
