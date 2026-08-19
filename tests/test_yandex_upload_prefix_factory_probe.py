"""Offline tests for targeted stage-one prefix factory analysis."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_factory_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_factory_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixFactoryProbeTests(unittest.TestCase):
    def test_target_composition_method_is_selected_by_hash_not_raw_name(self) -> None:
        # Use the real hash function to synthesize a method whose hash is then
        # substituted into the module-level target constant for this unit test.
        method = "minifiedMethod"
        original = probe.V21_METHOD_HASH
        probe.V21_METHOD_HASH = probe._hash_local("7644", method)  # noqa: SLF001
        try:
            result = probe._composition_target_method(  # noqa: SLF001
                f"class X{{{method}(value){{return this.customApiPrefixUrl||value}}}}"
            )
        finally:
            probe.V21_METHOD_HASH = original
        self.assertIsNotNone(result)
        encoded = json.dumps(result)
        self.assertIn("customApiPrefixUrl", result["anchors"])
        self.assertNotIn(method, encoded)

    def test_get_tld_host_export_role_normalizes_parameters(self) -> None:
        body = "r.d(exports,{getTldHost:()=>helper});function helper(base,tld,mark){return base+tld+mark;}"
        role = probe._export_function_role("91953", body, "getTldHost")  # noqa: SLF001
        self.assertEqual(role["export_key"], "getTldHost")
        self.assertEqual(role["parameter_count"], 3)
        flattened = [token for expr in role["normalized_returns"] for token in expr]
        self.assertIn("param:0", flattened)
        self.assertIn("param:1", flattened)
        self.assertIn("param:2", flattened)
        self.assertNotIn("base", json.dumps(role))

    def test_prefix_value_module_emits_only_public_yandex_literals(self) -> None:
        safe = probe._safe_yandex_literals(  # noqa: SLF001
            "const a='https://api.music.yandex.net';const b='PRIVATE_VALUE';const c='music.yandex.ru';"
        )
        self.assertIn("https://api.music.yandex.net", safe)
        self.assertIn("music.yandex.ru", safe)
        self.assertNotIn("PRIVATE_VALUE", safe)

    def test_export_symbols_are_hashed(self) -> None:
        body = "r.d(exports,{TLD_MARK:()=>hidden,getTldHost:()=>helper});"
        exports = probe._module_exports("91953", body)  # noqa: SLF001
        encoded = json.dumps(exports)
        self.assertIn("TLD_MARK", encoded)
        self.assertIn("getTldHost", encoded)
        self.assertNotIn("hidden", encoded)
        self.assertNotIn("helper", encoded)
        self.assertTrue(all(item["local_symbol_hash"].startswith("alias:") for item in exports))

    def test_analysis_never_returns_raw_module_source(self) -> None:
        composition = "class X{a(v){return this.prefixUrl||v}}"
        prefix_value = "r.d(exports,{A:()=>x});const x='https://music.yandex.ru';"
        helper = "r.d(exports,{getTldHost:()=>h,TLD_MARK:()=>m});function h(a,b,c){return a+b+c;}const m='PRIVATE_MARK';"
        result = probe.analyze_modules(composition, prefix_value, helper)
        encoded = json.dumps(result)
        self.assertNotIn("PRIVATE_MARK", encoded)
        self.assertNotIn("function h", encoded)
        self.assertNotIn("class X", encoded)


if __name__ == "__main__":
    unittest.main()
