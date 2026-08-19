"""Offline tests for secret-free Yandex upload runtime traces."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_runtime_trace.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_trace", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
trace = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(trace)


class YandexUploadRuntimeTraceTests(unittest.TestCase):
    def test_request_keeps_only_url_structure_and_header_names(self) -> None:
        event = {
            "method": "Network.requestWillBeSent",
            "params": {
                "timestamp": 123.0,
                "request": {
                    "method": "POST",
                    "url": "https://upload.music.yandex.net/loader/upload-url?uid=123&playlist-id=SECRET&token=BAD",
                    "headers": {
                        "Authorization": "OAuth VERY_SECRET",
                        "Cookie": "Session_id=VERY_SECRET",
                        "Content-Type": "application/json",
                        "X-Yandex-Music-Client": "PRIVATE_VALUE",
                    },
                },
            },
        }
        result = trace.sanitize_cdp_message(event)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["scheme"], "https")
        self.assertEqual(result["host"], "upload.music.yandex.net")
        self.assertEqual(result["path"], "/loader/upload-url")
        self.assertEqual(result["queryNames"], ["uid", "playlist-id"])
        self.assertIn("authorization", result["headerNames"])
        self.assertIn("cookie", result["headerNames"])
        self.assertTrue(result["authorization"]["present"])
        self.assertNotIn("VERY_SECRET", encoded)
        self.assertNotIn("PRIVATE_VALUE", encoded)
        self.assertNotIn("Session_id", encoded)
        self.assertNotIn("playlist-id=SECRET", encoded)

    def test_signed_url_query_values_never_survive(self) -> None:
        result = trace.sanitize_url(
            "https://storage.example.test/upload/abc?signature=SECRET&expires=100&x-retry-count=1"
        )
        encoded = json.dumps(result)
        self.assertEqual(result["path"], "/upload/abc")
        self.assertEqual(result["queryNames"], ["expires", "x-retry-count"])
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("signature", encoded)

    def test_response_body_shape_drops_signed_url_and_ids(self) -> None:
        result = trace.response_body_shape(
            json.dumps({"url": "https://signed.example/secret", "trackId": "123", "result": {"state": "processing"}})
        )
        encoded = json.dumps(result)
        self.assertIn('"url"', encoded)
        self.assertIn('"trackId"', encoded)
        self.assertNotIn("signed.example", encoded)
        self.assertNotIn("processing", encoded)
        self.assertNotIn('"123"', encoded)

    def test_runtime_payload_restricts_profile_and_auth_source(self) -> None:
        message = {
            "method": "Runtime.consoleAPICalled",
            "params": {
                "args": [
                    {
                        "value": trace.TRACE_PREFIX
                        + json.dumps(
                            {
                                "function": "getUploadUrl",
                                "clientRemoteType": "YandexMusicDesktopApp",
                                "authorizationSource": "custom-api-token",
                                "customApiPrefixSelected": True,
                                "customApiTokenPathSelected": True,
                                "ordinary": "DO_NOT_EMIT",
                            }
                        )
                    }
                ]
            },
        }
        result = trace.sanitize_cdp_message(message)
        encoded = json.dumps(result)
        self.assertEqual(result["clientRemoteType"], "YandexMusicDesktopApp")
        self.assertEqual(result["authorizationSource"], "custom-api-token")
        self.assertTrue(result["customApiPrefixSelected"])
        self.assertNotIn("ordinary", result)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_unknown_runtime_string_is_not_emitted(self) -> None:
        result = trace.sanitize_runtime_payload(
            {
                "function": "getUploadUrl;console.log('SECRET')",
                "clientRemoteType": "PRIVATE_PROFILE",
                "authorizationSource": "stolen-token",
            }
        )
        encoded = json.dumps(result)
        self.assertEqual(result["function"], "unknown")
        self.assertEqual(result["clientRemoteType"], "unknown")
        self.assertEqual(result["authorizationSource"], "unknown")
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("PRIVATE_PROFILE", encoded)
        self.assertNotIn("stolen-token", encoded)

    def test_report_declares_all_secret_classes_absent(self) -> None:
        report = trace.build_report([])
        self.assertTrue(report["safety"])
        self.assertTrue(all(value is False for value in report["safety"].values()))


if __name__ == "__main__":
    unittest.main()
