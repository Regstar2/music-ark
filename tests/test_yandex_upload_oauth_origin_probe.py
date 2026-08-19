"""Offline tests for stage-one OAuth origin tracing."""

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

_TOOL = _TOOLS / "yandex_upload_oauth_origin_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_oauth_origin_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadOauthOriginProbeTests(unittest.TestCase):
    def test_constructor_member_wiring_links_this_oauth(self) -> None:
        body = (
            'n.d(e,{X:()=>C});'
            'C=class{constructor(http,cfg){this.httpClient=http;this.oauth=cfg.oauth;}'
            'createRequestHeaders(){return {authorization:void 0!==this.oauth?"OAuth ".concat(this.oauth):void 0}}};'
        )
        result = probe.analyze_body(body)
        self.assertTrue(result["authorizationBindingFound"])
        origin = result["authorizationOrigin"]
        assert origin is not None
        self.assertEqual(origin["publicScheme"], "OAuth")
        self.assertIn("oauth", origin["thisProperties"])
        self.assertIn(
            {"property": "oauth", "source": {"kind": "constructor-param-member", "index": 1, "member": "oauth"}},
            origin["linkedConstructorAssignments"],
        )

    def test_direct_constructor_param_is_recognized(self) -> None:
        body = (
            'n.d(e,{X:()=>C});'
            'C=class{constructor(http,oauth){this.httpClient=http;}'
            'createRequestHeaders(){return {authorization:void 0!==oauth?"OAuth ".concat(oauth):void 0}}};'
        )
        result = probe.analyze_body(body)
        origin = result["authorizationOrigin"]
        assert origin is not None
        self.assertTrue(any(item["origin"] == {"kind": "constructor-param", "index": 1} for item in origin["bareAliases"]))

    def test_secret_scalar_never_emitted(self) -> None:
        body = (
            'n.d(e,{X:()=>C});'
            'C=class{constructor(a,b){this.oauth=b.oauth;const privateValue="DO_NOT_EMIT";}'
            'createRequestHeaders(){return {authorization:"OAuth "+this.oauth}}};'
        )
        encoded = json.dumps(probe.analyze_body(body), ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("privateValue", encoded)


if __name__ == "__main__":
    unittest.main()
