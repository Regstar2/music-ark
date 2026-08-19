"""Offline tests for the Chromium/Electron OAuth stage-one diagnostic probe."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_oauth_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_oauth_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class _Playlist:
    kind = 1055


class _FakeCdpClient:
    runtime_value: dict = {}
    last_expression: str = ""

    def __init__(self, url: str) -> None:
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def call(self, method: str, params=None, *, timeout: float = 5.0):  # noqa: ANN001
        if method == "Runtime.enable":
            return {}
        if method == "Runtime.evaluate":
            type(self).last_expression = str((params or {}).get("expression") or "")
            return {"result": {"type": "object", "value": dict(type(self).runtime_value)}}
        raise AssertionError(f"Unexpected CDP method: {method}")


class YandexUploadCdpOauthProbeTests(unittest.TestCase):
    def _args(self, file_path: Path) -> argparse.Namespace:
        return argparse.Namespace(
            base_dir=None,
            file=str(file_path),
            playlist_kind="1055",
            stage1_base_url="https://api.music.yandex.net",
            playlist_id_source="uuid",
            path_mode="full",
            confirm_owned_file=True,
            confirm_prepare=True,
            port=9222,
            target_contains="Yandex",
            launch_exe=None,
            launch_wait=0.0,
            timeout=10.0,
        )

    def _patch_common(self, file_path: Path):
        return (
            patch.object(probe.live, "_require_research_opt_in"),
            patch.object(
                probe.live,
                "_prepare_context",
                return_value=(object(), _Playlist(), file_path, "uid-secret", "playlist-uuid-secret", None),
            ),
            patch.object(probe.live, "_saved_token", return_value="oauth-secret"),
            patch.object(probe.groundtruth, "_launch_desktop"),
            patch.object(
                probe.groundtruth,
                "_discover_target",
                return_value={
                    "type": "page",
                    "title": "Yandex Music",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                },
            ),
            patch.object(probe.cdp, "CdpClient", _FakeCdpClient),
        )

    def test_success_proves_chromium_path_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": True,
                "httpStatus": 200,
                "responseShape": {
                    "type": "object",
                    "keys": {
                        "post-target": {"type": "string"},
                        "poll-result": {"type": "string"},
                        "ugc-track-id": {"type": "string"},
                    },
                },
                "postTargetPresent": True,
                "pollResultPresent": True,
                "ugcTrackIdPresent": True,
            }
            patches = self._patch_common(file_path)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                payload, code = probe.run(self._args(file_path))

            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "upload_url_obtained")
            self.assertEqual(payload["diagnosis"], "python-transport-mismatch-confirmed")
            self.assertTrue(payload["stage1"]["uploadUrlPresent"])
            self.assertFalse(payload["network"]["stage2Sent"])
            self.assertEqual(payload["network"]["browserCredentialsMode"], "omit")
            self.assertTrue(payload["safety"]["audio_bytes_sent"] is False)

            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("oauth-secret", serialized)
            self.assertNotIn("uid-secret", serialized)
            self.assertNotIn("playlist-uuid-secret", serialized)
            self.assertIn("credentials: 'omit'", _FakeCdpClient.last_expression)
            self.assertIn("oauth-secret", _FakeCdpClient.last_expression)

    def test_http_403_distinguishes_network_from_credential_or_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": True,
                "httpStatus": 403,
                "responseShape": {"type": "unavailable"},
                "postTargetPresent": False,
                "pollResultPresent": False,
                "ugcTrackIdPresent": False,
            }
            patches = self._patch_common(file_path)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                payload, code = probe.run(self._args(file_path))

            self.assertEqual(code, 3)
            self.assertTrue(payload["stage1"]["httpResponseReceived"])
            self.assertEqual(payload["stage1"]["httpStatus"], 403)
            self.assertEqual(payload["diagnosis"], "credential-or-required-request-profile-rejected")
            self.assertFalse(payload["stage1"]["desktopSessionCredentialsAttached"])

    def test_browser_network_error_reports_class_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": False,
                "errorName": "TypeError",
            }
            patches = self._patch_common(file_path)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                payload, code = probe.run(self._args(file_path))

            self.assertEqual(code, 3)
            self.assertEqual(payload["diagnosis"], "chromium-network-path-failed")
            self.assertEqual(payload["stage1"]["networkErrorClass"], "TypeError")
            self.assertIsNone(payload["stage1"]["httpStatus"])

    def test_parser_accepts_no_token_or_cookie_input(self) -> None:
        parser = probe.build_parser()
        options = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        self.assertIn("--stage1-base-url", options)
        self.assertIn("--launch-exe", options)
        self.assertNotIn("--token", options)
        self.assertNotIn("--oauth-token", options)
        self.assertNotIn("--cookie", options)
        self.assertNotIn("--session", options)

    def test_confirm_prepare_is_required_before_cdp_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            args = self._args(file_path)
            args.confirm_prepare = False
            with self.assertRaisesRegex(probe.YandexUploadProtocolError, "requires --confirm-prepare"):
                probe.run(args)


if __name__ == "__main__":
    unittest.main()
