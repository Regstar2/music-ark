"""Tests for the source-free Yandex upload contract-shape probe."""

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

_TOOL = _TOOLS / "yandex_upload_contract_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_contract_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadContractProbeTests(unittest.TestCase):
    def test_extracts_two_stage_contract_without_ordinary_strings(self) -> None:
        source = (
            'const privateLabel="do-not-report-this";'
            'async getUploadUrl(e){'
            'return this.httpClient.post("loader/upload-url", {'
            'searchParams:{"playlist-id":e},headers:{"x-retry-count":0}});'
            '}'
            'uploadFile(t,e,r){'
            'return this.httpClient.post(t,{body:e,headers:{"x-retry-count":r},'
            'signal:this.abortController.signal});'
            '}'
            'runUpload(){'
            'let e=await this.getUploadUrl(this.playlistId);'
            'let t=new FormData();t.append("file",this.file);'
            'return this.uploadFile(e.url,t,this.retry);'
            '}'
        )

        report = probe.analyze_contract(source)
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("do-not-report-this", encoded)

        self.assertIn({"name": "getUploadUrl", "params": ["e"]}, report["function_signatures"])
        self.assertIn({"name": "uploadFile", "params": ["t", "e", "r"]}, report["function_signatures"])

        first_stage = next(
            item
            for item in report["http_contracts"]
            if item["target"] == {"kind": "literal", "value": "loader/upload-url"}
        )
        self.assertEqual(first_stage["method"], "POST")
        self.assertEqual(first_stage["searchParams_keys"], ["playlist-id"])
        self.assertEqual(first_stage["headers_keys"], ["x-retry-count"])

        second_stage = next(
            item
            for item in report["http_contracts"]
            if item["target"] == {"kind": "identifier", "value": "t"}
        )
        self.assertTrue(second_stage["has_body"])
        self.assertTrue(second_stage["has_signal"])
        self.assertIn("x-retry-count", second_stage["headers_keys"])

        self.assertIn("file", report["form_fields"])
        self.assertIn("e.url", report["member_accesses"])
        self.assertIn(
            {
                "name": "uploadFile",
                "args": [
                    {"kind": "member", "value": "e.url"},
                    {"kind": "identifier", "value": "t"},
                    {"kind": "member", "value": "this.retry"},
                ],
            },
            report["named_invocations"],
        )

    def test_sensitive_names_are_not_emitted_as_object_keys(self) -> None:
        source = (
            'function uploadFile(t,e){return this.httpClient.post(t,{'
            'headers:{Authorization:"private",cookie:"private",' 
            '"x-retry-count":1},body:e})}'
        )
        encoded = json.dumps(probe.analyze_contract(source), ensure_ascii=False).lower()
        self.assertNotIn("authorization", encoded)
        self.assertNotIn("cookie", encoded)
        self.assertIn("x-retry-count", encoded)


if __name__ == "__main__":
    unittest.main()
