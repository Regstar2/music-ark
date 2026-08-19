"""Offline tests for stage-one header provenance tracing."""

from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_stage1_header_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_header_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1HeaderProbeTests(unittest.TestCase):
    def test_header_bindings_keep_names_and_semantics_without_values(self) -> None:
        body = (
            'const h={"x-request-id":ctx.requestId,'
            '"x-yandex-music-device":ctx.device,'
            '"x-yandex-music-without-invocation-info":ctx.withoutInvocationInfo,'
            '"authorization":ctx.oauth};'
        )
        bindings = probe._header_bindings("100", body)  # noqa: SLF001
        encoded = json.dumps(bindings)
        self.assertIn("x-request-id", encoded)
        self.assertIn("requestId", encoded)
        self.assertIn("x-yandex-music-device", encoded)
        self.assertIn("device", encoded)
        self.assertIn("withoutInvocationInfo", encoded)
        self.assertIn("oauth", encoded)
        self.assertNotIn("ctx", encoded)

    def test_module_report_lists_only_allowlisted_header_literals(self) -> None:
        body = (
            'const h={"x-request-id":requestId,"x-yandex-music-client":client,'
            '"x-private-debug":"DO_NOT_EMIT"};createRequestHeaders();'
        )
        report = probe._module_report("200", body)  # noqa: SLF001
        self.assertIsNotNone(report)
        assert report is not None
        self.assertIn("x-request-id", report["headersPresent"])
        self.assertIn("x-yandex-music-client", report["headersPresent"])
        encoded = json.dumps(report)
        self.assertNotIn("x-private-debug", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_dependency_path_is_numeric_structure_only(self) -> None:
        graph = defaultdict(set, {"12690": {"31322"}, "31322": {"91945"}})
        self.assertEqual(
            probe._shortest_path(graph, "12690", "91945"),  # noqa: SLF001
            ["12690", "31322", "91945"],
        )

    def test_missing_observed_headers_returns_none(self) -> None:
        self.assertIsNone(probe._module_report("1", 'const x="unrelated";'))  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
