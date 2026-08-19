"""Tests for CommonJS/object export forms of stage-one module 73202 hooks."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_hooks_object_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_hooks_object_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1HooksObjectProbeTests(unittest.TestCase):
    def test_module_exports_object_resolves_yandex_template(self) -> None:
        body = 'e.exports={hooks:x};x="https://api.music.yandex.{tld}"'
        result = probe.analyze_body(body)
        self.assertTrue(result["hooksObjectExportFound"])
        self.assertEqual(result["candidates"][0]["form"], "module-exports-object")
        self.assertEqual(result["candidates"][0]["chain"][1]["safeYandexTemplates"], ["https://api.music.yandex.{tld}"])

    def test_object_assign_form_is_supported_and_private_literal_redacted(self) -> None:
        body = 'Object.assign(t,{hooks:x});x="PRIVATE_INTERNAL_VALUE"'
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["hooksObjectExportFound"])
        self.assertNotIn("PRIVATE_INTERNAL_VALUE", encoded)

    def test_no_hooks_object_is_explicit(self) -> None:
        result = probe.analyze_body('e.exports={other:x}')
        self.assertFalse(result["hooksObjectExportFound"])
        self.assertEqual(result["candidates"], [])


if __name__ == "__main__":
    unittest.main()
