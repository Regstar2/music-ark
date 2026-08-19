"""Offline tests for the exact TLD helper export-lineage probe."""

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

_TOOL = _TOOLS / "yandex_upload_tld_lineage_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_tld_lineage_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadTldLineageProbeTests(unittest.TestCase):
    def test_reexport_lineage_reaches_function_without_local_names(self) -> None:
        index = {
            "91953": [{"body": 'var a=n(555);n.d(e,{getTldHost:()=>a.g,TLD_MARK:()=>a.M});'}],
            "555": [{"body": 'n.d(e,{g:()=>f,M:()=>m});f=(x,y,z)=>x.replace(z,y);m="{tld}";'}],
        }
        result = probe._resolve_export(index, "91953", "getTldHost")  # noqa: SLF001
        self.assertEqual(
            result["lineage"],
            [{
                "from_module_id": "91953",
                "from_export_key": "getTldHost",
                "to_module_id": "555",
                "to_export_key": "g",
            }],
        )
        self.assertEqual(result["terminal"]["kind"], "function")
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('"a"', encoded)
        self.assertNotIn('"f"', encoded)
        self.assertIn("param:0", encoded)

    def test_marker_lineage_emits_only_allowlisted_marker(self) -> None:
        index = {
            "91953": [{"body": 'var a=n(555);n.d(e,{TLD_MARK:()=>a.M});'}],
            "555": [{"body": 'n.d(e,{M:()=>m});m="{tld}";const secret="DO_NOT_EMIT";'}],
        }
        result = probe._resolve_export(index, "91953", "TLD_MARK")  # noqa: SLF001
        self.assertEqual(result["terminal"]["kind"], "value")
        self.assertEqual(result["terminal"]["safeLiterals"], ["{tld}"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_non_allowlisted_string_is_never_emitted(self) -> None:
        index = {"91953": [{"body": 'n.d(e,{TLD_MARK:()=>m});m="SUPER_SECRET_RANDOM_VALUE";'}]}
        result = probe._resolve_export(index, "91953", "TLD_MARK")  # noqa: SLF001
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("SUPER_SECRET_RANDOM_VALUE", encoded)
        self.assertEqual(result["terminal"].get("safeLiterals"), [])


if __name__ == "__main__":
    unittest.main()
