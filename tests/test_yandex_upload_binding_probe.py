"""Tests for the source-free Yandex upload function-binding probe."""

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

_TOOL = _TOOLS / "yandex_upload_binding_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_binding_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadBindingProbeTests(unittest.TestCase):
    def test_extracts_nested_request_bindings_without_source_values(self) -> None:
        source = (
            'const privateLabel="do-not-report-this";'
            'async getUploadUrl(t,e){'
            'return this.httpClient.post("loader/upload-url", {'
            'searchParams:{"playlist-id":t.playlistId,uid:t.uid,path:t.path},'
            'headers:{"x-retry-count":t.retryCount},...e});'
            '}'
            'uploadFile(t,e){'
            'return this.httpClient.post(t.url,{body:t.formData,signal:e.signal,'
            'headers:{"x-retry-count":t.retryCount}});'
            '}'
        )

        functions = probe.extract_function_bodies(source, ("getUploadUrl", "uploadFile"))
        encoded = json.dumps(functions, ensure_ascii=False)
        self.assertNotIn("do-not-report-this", encoded)

        get_upload = next(item for item in functions if item["name"] == "getUploadUrl")
        self.assertEqual(get_upload["params"], ["t", "e"])
        self.assertIn("t.playlistId", get_upload["parameter_member_accesses"])
        self.assertIn("t.uid", get_upload["parameter_member_accesses"])
        self.assertIn("t.path", get_upload["parameter_member_accesses"])
        self.assertIn(
            {"path": "searchParams.playlist-id", "value": {"kind": "member", "value": "t.playlistId"}},
            get_upload["object_bindings"],
        )
        self.assertIn(
            {"path": "searchParams.uid", "value": {"kind": "member", "value": "t.uid"}},
            get_upload["object_bindings"],
        )
        self.assertIn(
            {"path": "searchParams.path", "value": {"kind": "member", "value": "t.path"}},
            get_upload["object_bindings"],
        )

        upload = next(item for item in functions if item["name"] == "uploadFile")
        self.assertIn("t.url", upload["parameter_member_accesses"])
        self.assertIn("t.formData", upload["parameter_member_accesses"])
        self.assertIn("e.signal", upload["parameter_member_accesses"])
        self.assertIn(
            {"path": "body", "value": {"kind": "member", "value": "t.formData"}},
            upload["object_bindings"],
        )
        self.assertIn(
            {"path": "signal", "value": {"kind": "member", "value": "e.signal"}},
            upload["object_bindings"],
        )

    def test_sensitive_object_bindings_are_filtered(self) -> None:
        source = (
            'function uploadFile(t,e){return this.httpClient.post(t.url,{'
            'body:t.formData,Authorization:e.secret,cookie:e.cookie})}'
        )
        encoded = json.dumps(
            probe.extract_function_bodies(source, ("uploadFile",)),
            ensure_ascii=False,
        ).lower()
        self.assertNotIn("authorization", encoded)
        self.assertNotIn("cookie", encoded)
        self.assertNotIn("secret", encoded)
        self.assertIn("t.formdata", encoded)


if __name__ == "__main__":
    unittest.main()
