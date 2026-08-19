"""Offline tests for stage-one HTTP context and TLD origin tracing."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_context_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_context_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1ContextProbeTests(unittest.TestCase):
    def test_argument0_nearest_assignment_beats_initial_require_alias(self) -> None:
        body = 'var s=n(12690),ctx=n(74187);ctx=this.httpClient;new s.S(ctx,{prefixUrl:p});'
        result = probe.analyze_body(body)
        chain = result["argument0"]["chain"]
        self.assertEqual(chain[0]["sourceRefs"], [{"source_module_id": "74187", "export_key": "<module-object>"}])
        self.assertEqual(chain[1]["semanticThisPath"], ["this", "httpClient"])

    def test_tld_assignment_keeps_public_enum_only(self) -> None:
        body = 'var s=n(12690);this.tld="ru";const secret="DO_NOT_EMIT";new s.S(ctx,{prefixUrl:p});'
        result = probe.analyze_body(body)
        self.assertEqual(result["tldAssignments"][0]["publicTlds"], ["ru"])
        self.assertNotIn("DO_NOT_EMIT", json.dumps(result))

    def test_arbitrary_tld_string_is_not_emitted(self) -> None:
        body = 'var s=n(12690);this.tld="SUPER_PRIVATE";new s.S(ctx,{prefixUrl:p});'
        encoded = json.dumps(probe.analyze_body(body), ensure_ascii=False)
        self.assertNotIn("SUPER_PRIVATE", encoded)
        self.assertIn("<string>", encoded)


if __name__ == "__main__":
    unittest.main()
