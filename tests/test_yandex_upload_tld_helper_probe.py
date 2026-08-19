"""Offline tests for targeted getTldHost/prefix export analysis."""

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

_TOOL = _TOOLS / "yandex_upload_tld_helper_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_tld_helper_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadTldHelperProbeTests(unittest.TestCase):
    def test_named_get_tld_host_function_is_resolved(self) -> None:
        body = "r.d(exports,{getTldHost:()=>h});function h(base,tld,mark){return base+tld+mark;}"
        role = probe.resolve_function_export("91953", body, "getTldHost")
        self.assertEqual(role["definition"], "braced-function")
        self.assertEqual(role["parameter_count"], 3)
        flattened = [token for item in role["normalized_returns"] for token in item]
        self.assertIn("param:0", flattened)
        self.assertIn("param:1", flattened)
        self.assertIn("param:2", flattened)
        self.assertNotIn("base", json.dumps(role))

    def test_concise_arrow_get_tld_host_is_resolved(self) -> None:
        body = "r.d(exports,{getTldHost:()=>h});h=(base,tld,mark)=>base+tld+mark;"
        role = probe.resolve_function_export("91953", body, "getTldHost")
        self.assertEqual(role["definition"], "concise-arrow")
        self.assertEqual(role["parameter_count"], 3)
        self.assertIn("param:0", role["normalized_returns"][0])

    def test_public_yandex_host_template_is_allowed_without_queries(self) -> None:
        self.assertEqual(
            probe._safe_public_template("https://api.music.yandex.net"),  # noqa: SLF001
            "https://api.music.yandex.net",
        )
        self.assertEqual(
            probe._safe_public_template("https://music.yandex.{tld}/api"),  # noqa: SLF001
            "https://music.yandex.{tld}/api",
        )
        self.assertIsNone(probe._safe_public_template("https://music.yandex.ru/?token=SECRET"))  # noqa: SLF001
        self.assertIsNone(probe._safe_public_template("PRIVATE_VALUE"))  # noqa: SLF001

    def test_prefix_export_rhs_drops_ordinary_strings(self) -> None:
        body = "r.d(exports,{mZ:()=>x});const x='PRIVATE_VALUE';"
        value = probe.resolve_value_export("32732", body, "mZ")
        self.assertTrue(value["definitionFound"])
        self.assertEqual(value["normalizedRhs"], ["<string>"])
        self.assertEqual(value["publicYandexTemplates"], [])
        self.assertNotIn("PRIVATE_VALUE", json.dumps(value))

    def test_prefix_export_can_preserve_safe_yandex_template(self) -> None:
        body = "r.d(exports,{pp:()=>x});x='https://api.music.yandex.net';"
        value = probe.resolve_value_export("32732", body, "pp")
        self.assertIn("https://api.music.yandex.net", value["publicYandexTemplates"])

    def test_export_local_symbol_is_hashed(self) -> None:
        body = "r.d(exports,{TLD_MARK:()=>hidden});hidden='PRIVATE_MARK';"
        value = probe.resolve_value_export("91953", body, "TLD_MARK")
        encoded = json.dumps(value)
        self.assertTrue(value["local_symbol_hash"].startswith("alias:"))
        self.assertNotIn("hidden", encoded)
        self.assertNotIn("PRIVATE_MARK", encoded)


if __name__ == "__main__":
    unittest.main()
