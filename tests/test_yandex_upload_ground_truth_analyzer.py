"""Offline tests for sanitized upload ground-truth decisions."""

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

_TOOL = _TOOLS / "yandex_upload_ground_truth_analyzer.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_ground_truth_analyzer", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
analyzer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analyzer)


def _base(events):
    return {
        "format": "musicark-yandex-upload-cdp-runtime-report-v1",
        "events": events,
        "safety": {
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "raw_cdp_messages_included": False,
        },
    }


class YandexUploadGroundTruthAnalyzerTests(unittest.TestCase):
    def test_account_oauth_runtime_trace_becomes_direct_candidate(self) -> None:
        result = analyzer.analyze(
            _base(
                [
                    {
                        "event": "request",
                        "method": "POST",
                        "scheme": "https",
                        "host": "api.music.yandex.net",
                        "path": "/loader/upload-url",
                        "queryNames": ["uid", "playlist-id", "path"],
                        "headerNames": ["authorization", "x-yandex-music-client"],
                        "authorization": {"present": True, "source": "unknown"},
                    },
                    {
                        "event": "runtime",
                        "function": "m12690.Xc.getUploadUrl",
                        "clientRemoteType": "YandexMusicDesktopApp",
                        "authorizationSource": "account-oauth",
                        "customApiPrefixSelected": False,
                        "customApiTokenPathSelected": False,
                    },
                ]
            )
        )
        self.assertEqual(result["directHttpDecision"], "account-oauth-profile-candidate")
        self.assertEqual(result["stage1"]["hosts"], ["api.music.yandex.net"])
        self.assertEqual(result["runtime"]["clientRemoteTypes"], ["YandexMusicDesktopApp"])

    def test_custom_token_trace_blocks_direct_account_oauth_assumption(self) -> None:
        result = analyzer.analyze(
            _base(
                [
                    {
                        "event": "request",
                        "method": "POST",
                        "scheme": "https",
                        "host": "desktop.example.yandex.net",
                        "path": "/loader/upload-url",
                        "queryNames": ["uid"],
                        "headerNames": ["authorization"],
                        "authorization": {"present": True, "source": "unknown"},
                    },
                    {
                        "event": "runtime",
                        "function": "createHttpOptions",
                        "clientRemoteType": "YandexMusicDesktopApp",
                        "authorizationSource": "custom-api-token",
                        "customApiPrefixSelected": True,
                        "customApiTokenPathSelected": True,
                    },
                ]
            )
        )
        self.assertEqual(result["directHttpDecision"], "private-desktop-credential-path-observed")
        self.assertTrue(result["runtime"]["customApiTokenPathSelected"])

    def test_multipart_and_processing_are_summarized_without_values(self) -> None:
        result = analyzer.analyze(
            _base(
                [
                    {
                        "event": "request",
                        "method": "POST",
                        "scheme": "https",
                        "host": "upload.example.net",
                        "path": "/opaque",
                        "queryNames": [],
                        "headerNames": ["content-type"],
                        "contentTypeKind": "multipart-form-data",
                    },
                    {
                        "event": "request",
                        "method": "POST",
                        "scheme": "https",
                        "host": "music.yandex.net",
                        "path": "/ugc/tracks/processing",
                        "queryNames": [],
                        "headerNames": [],
                    },
                ]
            )
        )
        encoded = json.dumps(result)
        self.assertTrue(result["stage2"]["multipartPostObserved"])
        self.assertTrue(result["processing"]["requestObserved"])
        self.assertNotIn("SECRET", encoded)

    def test_unsafe_input_is_rejected(self) -> None:
        report = _base([])
        report["safety"]["authorization_values_included"] = True
        with self.assertRaisesRegex(ValueError, "safety"):
            analyzer.analyze(report)

    def test_no_stage1_observation_does_not_invent_profile(self) -> None:
        result = analyzer.analyze(_base([]))
        self.assertEqual(result["directHttpDecision"], "needs-runtime-stage1-observation")
        self.assertFalse(result["stage1"]["observed"])


if __name__ == "__main__":
    unittest.main()
