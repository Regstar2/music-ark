"""Offline tests for the sanitized Chromium stage-one failure-detail wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_failure_detail_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_failure_detail_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadCdpFailureDetailProbeTests(unittest.TestCase):
    def test_safe_net_error_keeps_only_normalized_chromium_enum(self) -> None:
        self.assertEqual(probe._safe_net_error("net::ERR_HTTP2_PROTOCOL_ERROR"), "NET::ERR_HTTP2_PROTOCOL_ERROR")  # noqa: SLF001
        self.assertEqual(probe._safe_net_error("secret diagnostic text"), "unknown")  # noqa: SLF001
        self.assertIsNone(probe._safe_net_error(None))  # noqa: SLF001

    def test_capture_keeps_header_names_and_failure_code_without_values(self) -> None:
        capture = probe._FailureCapture("https://api.music.yandex.net")  # noqa: SLF001
        capture.observe(
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "secret-request-id",
                    "request": {
                        "url": "https://api.music.yandex.net/loader/upload-url?uid=secret&playlist-id=secret&path=secret",
                        "method": "POST",
                        "headers": {
                            "Authorization": "OAuth secret-token",
                            "X-Yandex-Music-Client": "YandexMusicDesktopApp",
                            "User-Agent": "secret-user-agent",
                        },
                    },
                },
            }
        )
        capture.observe(
            {
                "method": "Network.loadingFailed",
                "params": {
                    "requestId": "secret-request-id",
                    "errorText": "net::ERR_HTTP2_PROTOCOL_ERROR",
                },
            }
        )
        payload = capture.payload()
        self.assertEqual(payload["postFailureCode"], "NET::ERR_HTTP2_PROTOCOL_ERROR")
        self.assertEqual(
            payload["postHeaderNames"],
            ["authorization", "user-agent", "x-yandex-music-client"],
        )
        serialized = str(payload)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("secret-request-id", serialized)
        self.assertNotIn("secret-user-agent", serialized)
        self.assertNotIn("uid=secret", serialized)

    def test_capture_separates_preflight_and_post(self) -> None:
        capture = probe._FailureCapture("https://api.music.yandex.net")  # noqa: SLF001
        for request_id, method in (("1", "OPTIONS"), ("2", "POST")):
            capture.observe(
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "requestId": request_id,
                        "request": {
                            "url": "https://api.music.yandex.net/loader/upload-url?x=redacted",
                            "method": method,
                            "headers": {"Accept": "application/json"},
                        },
                    },
                }
            )
        capture.observe(
            {
                "method": "Network.loadingFailed",
                "params": {"requestId": "2", "errorText": "net::ERR_CONNECTION_RESET"},
            }
        )
        payload = capture.payload()
        self.assertIsNone(payload["preflightFailureCode"])
        self.assertEqual(payload["postFailureCode"], "NET::ERR_CONNECTION_RESET")
        self.assertEqual(payload["preflightHeaderNames"], ["accept"])
        self.assertEqual(payload["postHeaderNames"], ["accept"])

    def test_unrelated_network_event_is_ignored(self) -> None:
        capture = probe._FailureCapture("https://api.music.yandex.net")  # noqa: SLF001
        capture.observe(
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "1",
                    "request": {
                        "url": "https://example.com/loader/upload-url",
                        "method": "POST",
                        "headers": {"Authorization": "secret"},
                    },
                },
            }
        )
        self.assertEqual(capture.payload()["postHeaderNames"], [])


if __name__ == "__main__":
    unittest.main()
