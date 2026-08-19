"""Tests for exact stage-one prefix use-site tracing."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_prefix_use_site_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_prefix_use_site_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1PrefixUseSiteProbeTests(unittest.TestCase):
    def test_reused_import_local_resolves_nearest_safe_template(self) -> None:
        body = (
            'a=n(12690),h=n(91953),p=n(32732),client=n(74187);'
            'const unrelated="DO_NOT_EMIT";'
            'p="https://api.music.yandex.{tld}";'
            'tld="ru";'
            'instance=new a.S(client,{prefixUrl:(0,h.getTldHost)(p,tld,h.TLD_MARK)});'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["stage1PrefixFound"])
        self.assertTrue(result["getTldHostCallFound"])
        arg0 = result["arguments"][0]["chain"]
        self.assertGreaterEqual(len(arg0), 2)
        self.assertEqual(arg0[0]["sourceRefs"], [{"source_module_id": "32732", "export_key": "<module-object>"}])
        self.assertEqual(arg0[1]["safeYandexTemplates"], ["https://api.music.yandex.{tld}"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_non_yandex_literal_is_structural_only(self) -> None:
        body = (
            'a=n(12690),h=n(91953),client=n(74187);'
            'p="PRIVATE_INTERNAL_VALUE";tld="ru";'
            'instance=new a.S(client,{prefixUrl:(0,h.getTldHost)(p,tld,h.TLD_MARK)});'
        )
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE_INTERNAL_VALUE", encoded)
        self.assertEqual(result["arguments"][0]["chain"][1]["safeYandexTemplates"], [])


if __name__ == "__main__":
    unittest.main()
