"""Offline tests for stage-one auth dependency lineage."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_auth_lineage_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_auth_lineage_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1AuthLineageProbeTests(unittest.TestCase):
    def test_constructor_arg0_resolves_http_client_module(self) -> None:
        body = 'var s=n(12690),h=n(74187);const x=new s.S(h,{prefixUrl:"DO_NOT_EMIT"});'
        result = probe._stage1_constructor(body)  # noqa: SLF001
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["argument0Source"], {"source_module_id": "74187", "export_key": "<module-object>"})
        self.assertEqual(result["argument1ConfigProperties"], ["prefixUrl"])
        self.assertFalse(result["customApiTokenPassedDirectly"])
        self.assertFalse(result["authorizationPassedDirectly"])
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))

    def test_direct_custom_token_is_classified_without_value(self) -> None:
        body = 'var s=n(12690),h=n(74187);const x=new s.S(h,{prefixUrl:p,customApiToken:secret});'
        result = probe._stage1_constructor(body)  # noqa: SLF001
        assert result is not None
        self.assertTrue(result["customApiTokenPassedDirectly"])
        encoded = json.dumps(result)
        self.assertNotIn("secret", encoded)

    def test_module_summary_contains_only_stable_structure(self) -> None:
        body = 'var a=n(37558);n.d(e,{X:()=>z});const secret="DO_NOT_EMIT";function z(){return a.createRequestHeaders()}'
        result = probe._module_summary("74187", body)  # noqa: SLF001
        self.assertIn("37558", result["import_module_ids"])
        self.assertIn("createRequestHeaders", result["anchors"])
        encoded = json.dumps(result)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn('"z"', encoded)


if __name__ == "__main__":
    unittest.main()
