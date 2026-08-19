"""Tests for the exact stage-one hooks export probe."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_hooks_export_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_hooks_export_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1HooksExportProbeTests(unittest.TestCase):
    def test_hooks_export_resolves_safe_yandex_template(self) -> None:
        body = (
            'r.d(t,{hooks:()=>x});'
            'const unrelated="DO_NOT_EMIT";'
            'x="https://api.music.yandex.{tld}";'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["exportFound"])
        self.assertEqual(result["exportKey"], "hooks")
        self.assertGreaterEqual(len(result["chain"]), 2)
        self.assertEqual(result["chain"][1]["safeYandexTemplates"], ["https://api.music.yandex.{tld}"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_hooks_export_redacts_non_yandex_literal(self) -> None:
        body = 'r.d(t,{hooks:()=>x});x="PRIVATE_INTERNAL_VALUE";'
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["exportFound"])
        self.assertNotIn("PRIVATE_INTERNAL_VALUE", encoded)
        self.assertEqual(result["chain"][1]["safeYandexTemplates"], [])

    def test_missing_hooks_export_is_explicit(self) -> None:
        result = probe.analyze_body('r.d(t,{other:()=>x});x="value";')
        self.assertEqual(result, {"exportFound": False})


if __name__ == "__main__":
    unittest.main()
