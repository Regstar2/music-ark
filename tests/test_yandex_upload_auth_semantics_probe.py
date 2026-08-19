"""Offline tests for stage-one authorization semantics."""

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

_TOOL = _TOOLS / "yandex_upload_auth_semantics_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_auth_semantics_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadAuthSemanticsProbeTests(unittest.TestCase):
    def test_authorization_binding_keeps_scheme_but_not_secret(self) -> None:
        body = (
            'n.d(e,{X:()=>C});'
            'C=class{createHttpOptions(a){const hidden="DO_NOT_EMIT";'
            'return {authorization:"OAuth "+credential,headers:a.headers,prefixUrl:a.prefixUrl}}};'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["classResolved"])
        self.assertTrue(result["authorizationBindings"])
        binding = result["authorizationBindings"][0]
        self.assertIn("OAuth", binding["publicSchemes"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("credential", encoded)

    def test_oauth_binding_reports_import_source_without_value(self) -> None:
        body = (
            'var h=n(91945);n.d(e,{X:()=>C});'
            'C=class{createRequestHeaders(){return {oauth:h.common,headers:h.common}}};'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["oauthBindings"])
        refs = result["oauthBindings"][0]["importMemberRefs"]
        self.assertIn({"source_module_id": "91945", "export_key": "common"}, refs)

    def test_custom_token_presence_is_boolean_only(self) -> None:
        body = (
            'n.d(e,{X:()=>C});'
            'C=class{createHttpOptions(a){const customApiToken=privateValue;return {headers:a.headers}}};'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["customApiTokenReferenced"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("privateValue", encoded)


if __name__ == "__main__":
    unittest.main()
