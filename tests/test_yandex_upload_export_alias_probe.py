"""Tests for the source-free V10 Yandex upload export/alias probe."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_export_alias_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_export_alias_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadExportAliasProbeTests(unittest.TestCase):
    def test_resolves_minified_export_to_imported_constructor(self) -> None:
        provider_body = (
            'n.d(t,{q:()=>A});'
            'A=class InternalClient{static marker="UgcUploadHttpClient";}'
        )
        importer_body = (
            'r=n(70204);'
            'const cfg={customApiPrefixUrl:c,customApiToken:SUPER_SECRET};'
            'const client=new r.q({prefixUrl:c,clientRemoteType:d});'
        )

        provider = {
            "module_id": "70204",
            "exports": probe._all_named_exports(provider_body),  # noqa: SLF001
            "anchor_symbol_relations": probe._anchor_symbol_relations(  # noqa: SLF001
                provider_body, "UgcUploadHttpClient"
            ),
        }
        uses = probe._alias_member_uses(importer_body, "r", "70204")  # noqa: SLF001

        self.assertEqual(provider["exports"], [{"export_name": "q", "symbol": "A"}])
        self.assertTrue(
            any(item.get("assigned_symbol") == "A" for item in provider["anchor_symbol_relations"])
        )
        self.assertIn("q", probe._resolved_export_names(provider))  # noqa: SLF001
        self.assertTrue(
            any(item["member"] == "q" and item["relation"] == "constructor" for item in uses)
        )

    def test_import_alias_scan_does_not_emit_secret_object_values(self) -> None:
        body = (
            'r=n(70204);'
            'const cfg={customApiPrefixUrl:c,customApiToken:VERY_PRIVATE_TOKEN};'
            'const x=new r.q(cfg);'
        )
        uses = probe._alias_member_uses(body, "r", "70204")  # noqa: SLF001
        encoded = json.dumps(uses, ensure_ascii=False)

        self.assertNotIn("VERY_PRIVATE_TOKEN", encoded)
        self.assertEqual(uses[0]["source_module_id"], "70204")
        self.assertEqual(uses[0]["member"], "q")
        self.assertEqual(uses[0]["relation"], "constructor")

    def test_sensitive_export_names_are_filtered(self) -> None:
        body = 'n.d(t,{customApiToken:()=>SECRET,q:()=>SafeClient});'
        exports = probe._all_named_exports(body)  # noqa: SLF001
        encoded = json.dumps(exports, ensure_ascii=False)

        self.assertNotIn("customApiToken", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertIn({"export_name": "q", "symbol": "SafeClient"}, exports)


if __name__ == "__main__":
    unittest.main()
