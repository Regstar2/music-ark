"""Offline tests for hashed upload runtime dataflow analysis."""

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

_TOOL = _TOOLS / "yandex_upload_runtime_dataflow_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_dataflow_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRuntimeDataflowProbeTests(unittest.TestCase):
    def test_tokenizer_drops_ordinary_string_contents(self) -> None:
        tokens = probe.tokenize(
            'const x="SUPER_SECRET"; const y=obj.customApiToken; const z={"authorization":y};'
        )
        encoded = json.dumps(tokens)
        self.assertNotIn("SUPER_SECRET", encoded)
        self.assertIn("customApiToken", tokens)
        self.assertIn("authorization", tokens)
        self.assertIn("<string>", tokens)

    def test_local_alias_is_hashed_in_target_path(self) -> None:
        body = "const minifiedAlias=config.customApiToken;const request={authorization:minifiedAlias};"
        result = probe.module_report("31322", body)
        self.assertIsNotNone(result)
        path = next(item["path"] for item in result["paths"] if item["source"] == "customApiToken")
        encoded = json.dumps(result)
        self.assertEqual(path[0], "customApiToken")
        self.assertEqual(path[-1], "authorization")
        self.assertTrue(any(node.startswith("alias:") for node in path))
        self.assertNotIn("minifiedAlias", encoded)

    def test_prefix_alias_path_is_structural_only(self) -> None:
        result = probe.module_report(
            "10",
            "let p=settings.customApiPrefixUrl;const cfg={prefixUrl:p};const ordinary='DO_NOT_EMIT';",
        )
        encoded = json.dumps(result)
        self.assertTrue(any(item["source"] == "customApiPrefixUrl" and item["sink"] == "prefixUrl" for item in result["paths"]))
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn('"p"', encoded)

    def test_unrelated_targets_without_path_do_not_invent_one(self) -> None:
        result = probe.module_report(
            "20",
            "function a(){return customApiToken;}function b(){return authorization;}",
        )
        self.assertIsNotNone(result)
        # Function-body braces stop the local expression graph from joining unrelated uses.
        self.assertFalse(any(item["source"] == "customApiToken" for item in result["paths"]))

    def test_alias_hash_is_module_scoped(self) -> None:
        self.assertNotEqual(probe._alias("1", "x"), probe._alias("2", "x"))  # noqa: SLF001
        self.assertTrue(probe._alias("1", "x").startswith("alias:"))  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
