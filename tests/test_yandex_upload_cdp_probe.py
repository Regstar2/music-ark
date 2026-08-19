"""Offline tests for the local Yandex desktop CDP upload probe."""

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

_TOOL = _TOOLS / "yandex_upload_cdp_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadCdpProbeTests(unittest.TestCase):
    def test_websocket_refuses_non_local_debugger(self) -> None:
        with self.assertRaisesRegex(probe.CdpProbeError, "non-local"):
            probe._LocalWebSocket("ws://example.com/devtools/page/1")  # noqa: SLF001

    def test_relevance_accepts_stage1_multipart_and_runtime(self) -> None:
        self.assertTrue(probe._is_relevant({"event": "request", "path": "/loader/upload-url", "host": "music.yandex.net"}))  # noqa: SLF001
        self.assertTrue(
            probe._is_relevant(  # noqa: SLF001
                {"event": "request", "method": "POST", "path": "/opaque", "host": "storage.example", "contentTypeKind": "multipart-form-data"}
            )
        )
        self.assertTrue(probe._is_relevant({"event": "runtime", "function": "getUploadUrl"}))  # noqa: SLF001
        self.assertFalse(probe._is_relevant({"event": "request", "method": "GET", "path": "/album/cover", "host": "music.yandex.ru"}))  # noqa: SLF001

    def test_target_metadata_strips_query_values(self) -> None:
        result = probe._safe_target_metadata(  # noqa: SLF001
            {"type": "page", "title": "Yandex Music", "url": "https://music.yandex.ru/home?token=SECRET&lang=ru"}
        )
        encoded = json.dumps(result)
        self.assertEqual(result["url"]["host"], "music.yandex.ru")
        self.assertEqual(result["url"]["queryNames"], ["lang"])
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("token", encoded)

    def test_report_contains_only_sanitized_events_and_safety_contract(self) -> None:
        report = probe.build_report(
            {"type": "page", "title": "Yandex Music", "url": "https://music.yandex.ru/"},
            [
                {
                    "event": "request",
                    "method": "POST",
                    "scheme": "https",
                    "host": "api.music.yandex.net",
                    "path": "/loader/upload-url",
                    "queryNames": ["uid", "playlist-id"],
                    "headerNames": ["authorization"],
                    "authorization": {"present": True, "source": "unknown"},
                }
            ],
            instrumentation_sha256="abc",
        )
        self.assertFalse(report["probe"]["networkMutationInitiatedByProbe"])
        self.assertFalse(report["probe"]["rawCdpPersisted"])
        self.assertTrue(all(value is False for value in report["safety"].values()))

    def test_instrumentation_source_never_reads_known_browser_secret_stores(self) -> None:
        source = (_TOOLS / "yandex_upload_runtime_instrumentation.js").read_text(encoding="utf-8")
        forbidden = (
            "document.cookie",
            "localStorage.getItem",
            "sessionStorage.getItem",
            "getAllCookies",
            "Network.getAllCookies",
            "Network.getCookies",
        )
        for value in forbidden:
            self.assertNotIn(value, source)
        self.assertIn("__MUSICARK_UPLOAD_TRACE__", source)
        self.assertIn("customApiTokenPathSelected", source)
        self.assertIn("authorizationSource", source)


if __name__ == "__main__":
    unittest.main()
