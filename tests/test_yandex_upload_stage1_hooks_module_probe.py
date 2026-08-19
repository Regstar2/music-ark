"""Tests for alternate webpack forms of stage-one module 73202 hooks."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_hooks_module_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_hooks_module_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1HooksModuleProbeTests(unittest.TestCase):
    def test_quoted_module_and_webpack_d_resolve_template(self) -> None:
        source = '"73202":(e,t,n)=>{n.d(t,{hooks:()=>x});x="https://api.music.yandex.{tld}"}'
        bodies = probe._extract_target_bodies(source)  # noqa: SLF001
        self.assertEqual(len(bodies), 1)
        result = probe.analyze_body(bodies[0])
        self.assertTrue(result["hooksExportFound"])
        self.assertTrue(result["exports"][0]["symbolResolved"])
        self.assertEqual(result["exports"][0]["chain"][1]["safeYandexTemplates"], ["https://api.music.yandex.{tld}"])

    def test_direct_assignment_resolves_symbol_without_emitting_private_literal(self) -> None:
        source = '73202:(e,t,n)=>{t.hooks=x;x="PRIVATE_INTERNAL_VALUE"}'
        body = probe._extract_target_bodies(source)[0]  # noqa: SLF001
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["hooksExportFound"])
        self.assertNotIn("PRIVATE_INTERNAL_VALUE", encoded)

    def test_unrelated_module_is_ignored(self) -> None:
        self.assertEqual(probe._extract_target_bodies('123:(e,t,n)=>{t.hooks=x}') , [])  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
