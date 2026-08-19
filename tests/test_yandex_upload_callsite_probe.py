"""Tests for the call-site focused Yandex upload ASAR probe."""

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

_TOOL = _TOOLS / "yandex_upload_callsite_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_callsite_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadCallsiteProbeTests(unittest.TestCase):
    def test_callsite_windows_link_first_and_second_upload_stages(self) -> None:
        source = (
            'const privateOrdinaryString="do-not-report-this";'
            'function getUploadUrl(playlistId){'
            'return this.httpClient.post("loader/upload-url", {'
            'headers:{"playlist-id":playlistId}});'
            '}'
            'function uploadFile(uploadUrl, body, retryCount){'
            'return this.httpClient.post(uploadUrl, {'
            'body:body, headers:{"content-type":"multipart/form-data",'
            '"x-retry-count":retryCount}});'
            '}'
        )

        sites = probe.analyze_member_text(
            source,
            names=("getUploadUrl", "uploadFile"),
            radius=600,
        )
        encoded = json.dumps(sites, ensure_ascii=False)

        self.assertNotIn("do-not-report-this", encoded)
        self.assertEqual({site["name"] for site in sites}, {"getUploadUrl", "uploadFile"})

        get_site = next(site for site in sites if site["name"] == "getUploadUrl")
        get_structure = get_site["window"]["structure"]
        self.assertIn(
            {"method": "POST", "target_kind": "literal", "target": "loader/upload-url"},
            get_structure["http_calls"],
        )
        self.assertIn("playlist-id", get_structure["protocol_literals"])

        upload_site = next(site for site in sites if site["name"] == "uploadFile")
        upload_structure = upload_site["window"]["structure"]
        self.assertIn(
            {"method": "POST", "target_kind": "identifier", "target": "uploadUrl"},
            upload_structure["http_calls"],
        )
        self.assertIn("multipart/form-data", upload_structure["mime_types"])
        self.assertIn("x-retry-count", upload_structure["protocol_literals"])

    def test_duplicate_names_are_deduplicated(self) -> None:
        sites = probe.analyze_member_text(
            "function getUploadUrl(){}",
            names=("getUploadUrl", "getUploadUrl"),
            radius=256,
        )
        self.assertEqual(len(sites), 1)


if __name__ == "__main__":
    unittest.main()
