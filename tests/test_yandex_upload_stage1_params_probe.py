"""Offline tests for the stage-one params/common/oauth provenance probe."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_params_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_params_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1ParamsProbeTests(unittest.TestCase):
    def test_params_common_oauth_shape_is_detected(self) -> None:
        body = (
            'var s=n(12690),a=n(10);'
            'const x=new s.S(client,{prefixUrl:p,params:{common:{oauth:a.value},other:"DO_NOT_EMIT"}});'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["stage1ConstructorFound"])
        self.assertTrue(result["paramsFound"])
        self.assertTrue(result["commonSemanticPresent"])
        self.assertTrue(result["oauthSemanticPresent"])
        self.assertIn("oauth", result["params"]["common"]["objectKeys"])
        oauth_source = next(item for item in result["params"]["common"]["propertySources"] if item["key"] == "oauth")
        self.assertEqual(oauth_source["sourceRefs"], [{"source_module_id": "10", "export_key": "value"}])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertIn('"source_module_id": "10"', encoded)

    def test_params_module_member_source_is_stable(self) -> None:
        body = 'var s=n(12690),a=n(55);new s.S(client,{params:{common:a.common}});'
        result = probe.analyze_body(body)
        refs = result["params"]["common"]["sourceRefs"]
        self.assertIn({"source_module_id": "55", "export_key": "common"}, refs)

    def test_sensitive_property_name_is_filtered(self) -> None:
        body = 'var s=n(12690),a=n(55);new s.S(client,{params:{common:{oauth:a.common,token:a.secret}}});'
        result = probe.analyze_body(body)
        keys = result["params"]["common"]["objectKeys"]
        self.assertIn("oauth", keys)
        self.assertNotIn("token", keys)
        self.assertNotIn("secret", json.dumps(result))

    def test_no_params_is_reported_without_source_output(self) -> None:
        body = 'var s=n(12690);const secret="DO_NOT_EMIT";new s.S(client,{prefixUrl:p});'
        result = probe.analyze_body(body)
        self.assertEqual(result, {"stage1ConstructorFound": True, "paramsFound": False})
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
