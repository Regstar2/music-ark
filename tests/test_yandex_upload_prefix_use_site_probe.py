"""Offline tests for exact prefix use-site assignment tracing."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_use_site_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_use_site_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixUseSiteProbeTests(unittest.TestCase):
    def test_nearest_reassignment_overrides_initial_import_meaning(self) -> None:
        body = (
            'var h=n(91953),p=n(32732);'
            'p="https://api.music.yandex.{tld}";'
            'const x=(0,h.getTldHost)(p,t,h.TLD_MARK);'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["callFound"])
        arg0 = result["arguments"][0]
        self.assertGreaterEqual(len(arg0["chain"]), 2)
        self.assertEqual(arg0["chain"][1]["safeYandexTemplates"], ["https://api.music.yandex.{tld}"])

    def test_unrelated_string_never_escapes(self) -> None:
        body = 'var h=n(91953);let p="DO_NOT_EMIT";(0,h.getTldHost)(p,t,h.TLD_MARK);'
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertIn("<string>", encoded)

    def test_alias_chain_is_hashed_not_named(self) -> None:
        body = 'var h=n(91953);let a=b,b=c;(0,h.getTldHost)(a,t,h.TLD_MARK);'
        result = probe.analyze_body(body)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('"a"', encoded)
        self.assertNotIn('"b"', encoded)


if __name__ == "__main__":
    unittest.main()
