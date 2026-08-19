"""Offline tests for targeted stage-one export/config role resolution."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_role_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_role_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1RoleProbeTests(unittest.TestCase):
    def test_export_role_maps_class_to_upload_anchors(self) -> None:
        stage1 = (
            "r.d(exports,{S:()=>Upload});"
            "Upload=class extends Base{getUploadUrl(){return this.httpClient.post('loader/upload-url')}};"
        )
        composition = "const api=req(12690);const x=new api.S(core,{prefixUrl:p});"
        result = probe.analyze_modules(stage1, composition)
        role = next(item for item in result["stage1_export_roles"] if item["export_key"] == "S")
        self.assertEqual(role["definition"], "class")
        self.assertIn("getUploadUrl", role["role_anchors"])
        self.assertIn("loader/upload-url", role["role_anchors"])

    def test_constructor_object_map_links_provider_export_without_value_strings(self) -> None:
        stage1 = "r.d(exports,{S:()=>Upload});Upload=class{getUploadUrl(){}};"
        composition = (
            "const api=req(12690),provider=req(70204);"
            "const x=new api.S(core,{prefixUrl:p,ugcUploadClient:provider.Xc,ordinaryThing:provider.RG,customApiToken:secret});"
        )
        result = probe.analyze_modules(stage1, composition)
        call = result["stage1_constructor_calls"][0]
        object_arg = call["object_arguments"][0]
        properties = object_arg["properties"]
        ugc = next(item for item in properties if item["key"] == "ugcUploadClient")
        self.assertEqual(ugc["value"]["source_refs"], [{"source_module_id": "70204", "export_key": "Xc"}])
        generic = next(item for item in properties if item["value"]["source_refs"] == [{"source_module_id": "70204", "export_key": "RG"}])
        self.assertTrue(generic["key"].startswith("key:"))
        encoded = json.dumps(result)
        self.assertNotIn("ordinaryThing", encoded)
        self.assertNotIn("secret", encoded)

    def test_protocol_keys_preserved_generic_keys_hashed(self) -> None:
        mapped = probe._object_map(  # noqa: SLF001
            "7644",
            "{httpClient:a,prefixUrl:b,normalField:c}",
            [],
        )
        keys = [item["key"] for item in mapped]
        self.assertIn("httpClient", keys)
        self.assertIn("prefixUrl", keys)
        self.assertTrue(any(key.startswith("key:") for key in keys))
        self.assertNotIn("normalField", keys)

    def test_local_identifiers_are_hashed_in_value_summary(self) -> None:
        summary = probe._value_summary(  # noqa: SLF001
            "7644",
            "localSecretAlias",
            [],
        )
        encoded = json.dumps(summary)
        self.assertEqual(summary["kind"], {"kind": "identifier"})
        self.assertTrue(summary["alias_refs"][0].startswith("alias:"))
        self.assertNotIn("localSecretAlias", encoded)

    def test_source_module_reference_uses_stable_export_key(self) -> None:
        imports = [{"local": "provider", "source_module_id": "70204"}]
        summary = probe._value_summary(  # noqa: SLF001
            "7644",
            "provider.RG",
            imports,
        )
        self.assertEqual(summary["source_refs"], [{"source_module_id": "70204", "export_key": "RG"}])
        self.assertNotIn("provider", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
