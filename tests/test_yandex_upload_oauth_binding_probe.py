"""Offline tests for stage-one OAuth local binding lineage."""

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

_TOOL = _TOOLS / "yandex_upload_oauth_binding_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_oauth_binding_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadOauthBindingProbeTests(unittest.TestCase):
    def test_destructured_oauth_source_is_resolved(self) -> None:
        body = (
            'n.d(e,{X:()=>C});C=class{constructor(a,b){this.config=b;}'
            'createRequestHeaders(){let {oauth:x}=this.config;'
            'return {authorization:void 0!==x?"OAuth ".concat(x):void 0}}};'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["authorizationLocalResolved"])
        self.assertEqual(
            result["source"],
            {"kind": "object-destructure", "property": "oauth", "sourcePath": ["this", "config"], "sourceNormalized": None},
        )

    def test_simple_this_member_assignment_is_resolved(self) -> None:
        body = (
            'n.d(e,{X:()=>C});C=class{createRequestHeaders(){let x=this.oauth;'
            'return {authorization:"OAuth ".concat(x)}}};'
        )
        result = probe.analyze_body(body)
        self.assertEqual(result["source"], {"kind": "this-member", "path": ["this", "oauth"]})

    def test_sensitive_scalar_and_local_name_never_emit(self) -> None:
        body = (
            'n.d(e,{X:()=>C});C=class{createRequestHeaders(){let privateLocal="DO_NOT_EMIT";'
            'return {authorization:"OAuth ".concat(privateLocal)}}};'
        )
        encoded = json.dumps(probe.analyze_body(body), ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("privateLocal", encoded)


if __name__ == "__main__":
    unittest.main()
