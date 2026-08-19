"""Offline tests for getTldHost standard-method semantics."""

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

_TOOL = _TOOLS / "yandex_upload_tld_method_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_tld_method_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadTldMethodProbeTests(unittest.TestCase):
    def test_resolves_replace_semantics(self) -> None:
        body = 'n.d(e,{getTldHost:()=>f});f=(template,tld,mark)=>template.replace(mark,tld);'
        result = probe._get_tld_method(body)  # noqa: SLF001
        self.assertTrue(result["resolved"])
        self.assertEqual(result["method"], "replace")
        self.assertEqual(result["parameterCount"], 3)

    def test_non_allowlisted_method_name_is_redacted(self) -> None:
        body = 'n.d(e,{getTldHost:()=>f});f=(template,tld,mark)=>template.secretMethod(mark,tld);'
        result = probe._get_tld_method(body)  # noqa: SLF001
        self.assertFalse(result["resolved"])
        self.assertEqual(result["method"], "non-allowlisted")
        self.assertNotIn("secretMethod", json.dumps(result))

    def test_stage1_call_classifies_module_sources_only(self) -> None:
        body = 'var h=n(91953),p=n(32732);const secret="DO_NOT_EMIT";const x=(0,h.getTldHost)(p,t,h.TLD_MARK);'
        result = probe._get_tld_call(body)  # noqa: SLF001
        assert result is not None
        self.assertEqual(result["arguments"][0], {"kind": "webpack-source", "source_module_id": "32732", "export_key": "<module-object>"})
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
