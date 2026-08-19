"""Offline tests for exact stage-one prefix import-binding resolution."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_import_binding_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_import_binding_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixImportBindingProbeTests(unittest.TestCase):
    def test_require_member_chain_preserves_named_export(self) -> None:
        chain = probe._require_chain("req(32732).pp.from(config)", "req", "32732")  # noqa: SLF001
        self.assertEqual(chain, ["pp", "from"])

    def test_stage1_prefix_binding_reports_full_rhs_not_only_module_id(self) -> None:
        body = (
            "const api=req(12690),helper=req(91953),base=req(32732).pp.from(cfg);"
            "const client=new api.S(core,{prefixUrl:(0,helper.getTldHost)(base,tld,helper.TLD_MARK)});"
        )
        result = probe.analyze_composition(body)
        self.assertTrue(result["stage1PrefixFound"])
        binding = next(item for item in result["bindings"] if item["source_module_id"] == "32732")
        self.assertEqual(binding["requireMemberChain"], ["pp", "from"])
        encoded = json.dumps(binding)
        self.assertIn("m32732.pp", encoded)
        self.assertNotIn("base", encoded)
        self.assertNotIn("cfg", encoded)

    def test_module_object_binding_is_reported_without_fake_export(self) -> None:
        body = (
            "const api=req(12690),helper=req(91953),base=req(32732);"
            "new api.S(core,{prefixUrl:(0,helper.getTldHost)(base,tld,helper.TLD_MARK)});"
        )
        result = probe.analyze_composition(body)
        binding = next(item for item in result["bindings"] if item["source_module_id"] == "32732")
        self.assertEqual(binding.get("requireMemberChain"), [])
        self.assertIn("m32732", binding["normalizedRhs"])

    def test_unrelated_imports_are_not_emitted(self) -> None:
        body = (
            "const api=req(12690),helper=req(91953),base=req(32732),unrelated=req(55555);"
            "new api.S(core,{prefixUrl:(0,helper.getTldHost)(base,tld,helper.TLD_MARK)});"
        )
        result = probe.analyze_composition(body)
        self.assertFalse(any(item["source_module_id"] == "55555" for item in result["bindings"]))

    def test_local_aliases_never_survive_output(self) -> None:
        body = (
            "const api=req(12690),helper=req(91953),veryLocalName=req(32732).mZ;"
            "new api.S(core,{prefixUrl:(0,helper.getTldHost)(veryLocalName,tld,helper.TLD_MARK)});"
        )
        result = probe.analyze_composition(body)
        encoded = json.dumps(result)
        self.assertNotIn("veryLocalName", encoded)
        self.assertIn("mZ", encoded)


if __name__ == "__main__":
    unittest.main()
