"""Offline tests for targeted upload composition-root tracing."""

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

_TOOL = _TOOLS / "yandex_upload_runtime_composition_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_composition_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRuntimeCompositionProbeTests(unittest.TestCase):
    def test_imported_constructor_reports_source_and_config_shape_without_local_names(self) -> None:
        body = (
            "const provider=req(70204),cfg=req(37558);"
            "const localConfig={customApiPrefixUrl:a,customApiToken:b};"
            "const client=new provider.Xc(localConfig,{clientRemoteType:c});"
        )
        result = probe.analyze_module(body)
        encoded = json.dumps(result)
        call = next(item for item in result["imported_calls"] if item["source_module_id"] == "70204")
        self.assertEqual(call["export_key"], "Xc")
        self.assertEqual(call["relation"], "constructor")
        self.assertEqual(call["argument_count"], 2)
        self.assertTrue(any(arg["config_properties"] == ["clientRemoteType"] for arg in call["arguments"]))
        self.assertNotIn("localConfig", encoded)
        self.assertNotIn('"a"', encoded)
        self.assertNotIn('"b"', encoded)
        self.assertNotIn('"c"', encoded)

    def test_config_property_to_argument_alias_path_is_reported(self) -> None:
        body = (
            "const provider=req(70204);"
            "const configAlias=settings.customApiPrefixUrl;"
            "const client=new provider.RG(configAlias);"
        )
        result = probe.analyze_module(body)
        call = next(item for item in result["imported_calls"] if item["source_module_id"] == "70204")
        self.assertTrue(
            any(
                item["property"] == "customApiPrefixUrl"
                and item["argument_alias"].startswith("alias:")
                for item in call["config_paths_to_arguments"]
            )
        )

    def test_member_uses_expose_stable_export_key_not_import_local(self) -> None:
        body = "const hidden=req(12690);const x=hidden.Xc;const y=hidden.RG;"
        result = probe.analyze_module(body)
        encoded = json.dumps(result)
        uses = {(item["source_module_id"], item["export_key"]) for item in result["imported_member_uses"]}
        self.assertIn(("12690", "Xc"), uses)
        self.assertIn(("12690", "RG"), uses)
        self.assertNotIn("hidden", encoded)

    def test_ordinary_strings_never_appear_in_output(self) -> None:
        body = "const provider=req(70204);const ordinary='SUPER_SECRET';new provider.Xc({prefixUrl:ordinary});"
        result = probe.analyze_module(body)
        encoded = json.dumps(result)
        self.assertNotIn("SUPER_SECRET", encoded)
        self.assertIn("prefixUrl", encoded)

    def test_unrelated_imports_are_not_selected(self) -> None:
        body = "const unrelated=req(99999),provider=req(70204);unrelated.A();provider.Xc();"
        result = probe.analyze_module(body)
        self.assertEqual(result["selected_imports"], [{"source_module_id": "70204"}])
        self.assertFalse(any(item["source_module_id"] == "99999" for item in result["imported_calls"]))


if __name__ == "__main__":
    unittest.main()
