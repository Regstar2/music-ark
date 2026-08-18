"""Tests for the source-free V12 Yandex upload symbol graph probe."""

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

_TOOL = _TOOLS / "yandex_upload_symbol_graph_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_symbol_graph_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadSymbolGraphProbeTests(unittest.TestCase):
    def test_resolves_export_alias_chain_to_upload_anchor_owner(self) -> None:
        source = (
            'n.d(e,{Xc:()=>A,RG:()=>B});'
            'C=class{getUploadUrl(){return "loader/upload-url"} uploadFile(){}};'
            'A=C;'
            'B=class{createHttpOptions(){return 1}};'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        by_name = {item["export_name"]: item for item in record["export_paths"]}

        self.assertEqual(by_name["Xc"]["path"], ["A", "C"])
        self.assertIn("getUploadUrl", by_name["Xc"]["target_anchors"])
        self.assertIn("loader/upload-url", by_name["Xc"]["target_anchors"])
        self.assertEqual(by_name["RG"]["path"], ["B"])
        self.assertIn("createHttpOptions", by_name["RG"]["target_anchors"])

    def test_named_class_can_be_anchor_owner(self) -> None:
        source = (
            'n.d(e,{Xc:()=>Client,RG:()=>Other});'
            'class Client{getUploadUrl(){return "loader/upload-url"}}'
            'class Other{}'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        by_name = {item["export_name"]: item for item in record["export_paths"]}
        self.assertEqual(by_name["Xc"]["path"], ["Client"])
        self.assertEqual(by_name["RG"]["path"], [])

    def test_sensitive_values_and_ordinary_strings_are_not_emitted(self) -> None:
        source = (
            'n.d(e,{Xc:()=>A,RG:()=>B});'
            'const customApiToken="SUPER_SECRET";'
            'A=class{getUploadUrl(){return "loader/upload-url"}};'
            'B="ORDINARY_STRING";'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        encoded = json.dumps(record, ensure_ascii=False)

        self.assertNotIn("SUPER_SECRET", encoded)
        self.assertNotIn("ORDINARY_STRING", encoded)
        self.assertNotIn("customApiToken", encoded)


if __name__ == "__main__":
    unittest.main()
