"""Offline tests for exact normalized stage-one prefix provenance."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_provenance_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_provenance_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixProvenanceProbeTests(unittest.TestCase):
    def test_normalized_expression_keeps_module_refs_and_hashes_locals(self) -> None:
        imports = [{"local": "host", "source_module_id": "91953"}]
        tokens = probe._normalized_expression(  # noqa: SLF001
            "7644",
            "localPrefix || host.getTldHost() + host.TLD_MARK",
            imports,
        )
        encoded = json.dumps(tokens)
        self.assertIn("m91953.getTldHost", tokens)
        self.assertIn("m91953.TLD_MARK", tokens)
        self.assertIn("||", tokens)
        self.assertTrue(any(item.startswith("alias:") for item in tokens))
        self.assertNotIn("localPrefix", encoded)

    def test_public_yandex_literal_is_allowed_but_query_values_are_removed(self) -> None:
        tokens = probe._normalized_expression(  # noqa: SLF001
            "7644",
            "'https://api.music.yandex.net/path?token=SECRET'",
            [],
        )
        encoded = json.dumps(tokens)
        self.assertEqual(tokens, ["<string>"])
        self.assertNotIn("SECRET", encoded)

        public = probe._normalized_expression(  # noqa: SLF001
            "7644",
            "'https://api.music.yandex.net/path'",
            [],
        )
        self.assertEqual(public, ["literal:https://api.music.yandex.net/path"])

    def test_stage1_prefix_is_extracted_from_exact_constructor_object(self) -> None:
        body = (
            "const api=req(12690),host=req(91953);"
            "const fallback=host.getTldHost()+host.TLD_MARK;"
            "const client=new api.S(core,{prefixUrl:fallback,retryPolicyConfig:r});"
        )
        result = probe.analyze_composition(body)
        self.assertTrue(result["stage1PrefixFound"])
        self.assertTrue(any(item.startswith("alias:") for item in result["normalizedStage1Prefix"]))
        provenance = result["aliasProvenance"]
        self.assertTrue(any("m91953.getTldHost" in item.get("normalizedRhs", []) for item in provenance))

    def test_custom_token_binding_never_emits_value(self) -> None:
        body = "const privateAlias='SUPER_SECRET';const cfg={customApiToken:privateAlias};"
        result = probe.analyze_composition(body)
        encoded = json.dumps(result)
        binding = next(item for item in result["configPropertyBindings"] if item["property"] == "customApiToken")
        self.assertTrue(binding["normalizedRhs"][0].startswith("alias:"))
        self.assertNotIn("privateAlias", encoded)
        self.assertNotIn("SUPER_SECRET", encoded)

    def test_assignment_map_does_not_return_raw_alias_names(self) -> None:
        body = "const alpha=beta+gamma;const unrelated='DO_NOT_EMIT';"
        assignments = probe._assignment_map(body)  # noqa: SLF001
        result = probe._alias_provenance("7644", ["alpha"], assignments, [], max_depth=2)  # noqa: SLF001
        encoded = json.dumps(result)
        self.assertNotIn("alpha", encoded)
        self.assertNotIn("beta", encoded)
        self.assertNotIn("gamma", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertTrue(result[0]["alias"].startswith("alias:"))


if __name__ == "__main__":
    unittest.main()
