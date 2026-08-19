"""Offline tests for the stage-one request-stack probe."""

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

_TOOL = _TOOLS / "yandex_upload_request_stack_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_request_stack_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRequestStackProbeTests(unittest.TestCase):
    def test_follows_imported_class_extends_chain(self) -> None:
        index = {
            "12690": 'var b=n(31322);n.d(e,{S:()=>A});A=class extends b.X{getUploadUrl(){return this.createHttpOptions({})}};',
            "31322": 'var c=n(38208);n.d(e,{X:()=>B});B=class extends c.Y{createHttpOptions(x){return {headers:x.headers,authorization:x.authorization}}};',
            "38208": 'n.d(e,{Y:()=>C});C=class{constructor(httpClient){this.httpClient=httpClient}};',
        }
        stack = probe._follow_stack(index)  # noqa: SLF001
        self.assertEqual([(item["module_id"], item["export_key"]) for item in stack], [("12690", "S"), ("31322", "X"), ("38208", "Y")])
        self.assertIn("authorization", stack[1]["allowlistedNames"])
        encoded = json.dumps(stack)
        self.assertNotIn("httpClient){", encoded)

    def test_constructor_summary_exposes_only_allowlisted_param_wiring(self) -> None:
        fragment = 'class X{constructor(a,b){this.httpClient=a;this.prefixUrl=b;this.x="DO_NOT_EMIT"}}'
        result = probe._constructor_summary("1", fragment)  # noqa: SLF001
        assert result is not None
        self.assertIn({"property": "httpClient", "source": "param:0"}, result["allowlistedAssignments"])
        self.assertIn({"property": "prefixUrl", "source": "param:1"}, result["allowlistedAssignments"])
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))

    def test_method_summary_keeps_import_refs_without_values(self) -> None:
        body = 'var h=n(91945);n.d(e,{X:()=>C});C=class{createHttpOptions(a){const secret="DO_NOT_EMIT";return {headers:h.makeHeaders(a),authorization:a.authorization}}};'
        found = probe._class_span(body, "X")  # noqa: SLF001
        assert found is not None
        _, _, fragment = found
        result = probe._method_summary("31322", body, fragment, "createHttpOptions")  # noqa: SLF001
        assert result is not None
        self.assertIn({"source_module_id": "91945", "export_key": "makeHeaders"}, result["importMemberRefs"])
        self.assertIn("authorization", result["allowlistedNames"])
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
