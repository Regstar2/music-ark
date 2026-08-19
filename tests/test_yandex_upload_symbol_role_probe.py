"""Tests for the source-free V11 Yandex upload symbol-role probe."""

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

_TOOL = _TOOLS / "yandex_upload_symbol_role_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_symbol_role_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadSymbolRoleProbeTests(unittest.TestCase):
    def test_maps_target_exports_to_protocol_role_anchors(self) -> None:
        source = (
            'n.d(e,{Xc:()=>Client,RG:()=>Other});'
            'Client=class{getUploadUrl(){return "loader/upload-url"} uploadFile(){}};'
            'Other=class{createHttpOptions(){return 1}};'
        )

        roles = probe._provider_export_roles(source, ["Xc", "RG"])  # noqa: SLF001
        by_name = {item["export_name"]: item for item in roles}

        self.assertIn("Xc", by_name)
        self.assertIn("RG", by_name)
        self.assertIn("loader/upload-url", by_name["Xc"]["role_anchors"])
        self.assertIn("getUploadUrl", by_name["Xc"]["role_anchors"])
        self.assertIn("uploadFile", by_name["Xc"]["role_anchors"])
        self.assertNotIn("loader/upload-url", by_name["RG"]["role_anchors"])

    def test_importer_context_is_structural_only(self) -> None:
        source = 'const cfg={httpClient:r.Xc,other:r.RG};use(r.Xc);const x=r.RG;'

        xc = probe._importer_use_context(source, "r", "Xc")  # noqa: SLF001
        rg = probe._importer_use_context(source, "r", "RG")  # noqa: SLF001
        encoded = json.dumps({"xc": xc, "rg": rg}, ensure_ascii=False)

        self.assertTrue(xc)
        self.assertTrue(rg)
        self.assertNotIn("httpClient", encoded)
        self.assertNotIn("other", encoded)
        self.assertNotIn("const x", encoded)

    def test_unrelated_secret_values_are_never_emitted(self) -> None:
        source = (
            'n.d(e,{Xc:()=>Client,RG:()=>Other});'
            'const customApiToken="SUPER_SECRET_TOKEN";'
            'Client=class{getUploadUrl(){return "loader/upload-url"}};'
            'Other=class{};'
        )
        roles = probe._provider_export_roles(source, ["Xc", "RG"])  # noqa: SLF001
        encoded = json.dumps(roles, ensure_ascii=False)

        self.assertNotIn("SUPER_SECRET_TOKEN", encoded)


if __name__ == "__main__":
    unittest.main()
