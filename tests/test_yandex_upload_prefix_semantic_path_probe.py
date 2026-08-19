"""Offline tests for semantic stage-one prefix config paths."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_semantic_path_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_semantic_path_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixSemanticPathProbeTests(unittest.TestCase):
    def test_exact_config_host_and_tld_paths_are_emitted(self) -> None:
        body = 'var h=n(91953);const x=(0,h.getTldHost)(this.config.musicApi.host,this.tld,h.TLD_MARK);'
        result = probe.analyze_body(body)
        self.assertEqual(result["hostConfigPath"], ["this", "config", "musicApi", "host"])
        self.assertEqual(result["tldPath"], ["this", "tld"])
        self.assertTrue(result["hostShapeValid"])
        self.assertTrue(result["tldShapeValid"])

    def test_optional_chain_lowering_recovers_static_schema_key(self) -> None:
        body = (
            'var h=n(91953);const x=(0,h.getTldHost)('
            '(null==(q=this.config.loaderApi)?void 0:q.host),this.tld,h.TLD_MARK);'
        )
        result = probe.analyze_body(body)
        self.assertEqual(result["hostConfigPath"], ["this", "config", "loaderApi", "host"])
        self.assertTrue(result["hostShapeValid"])

    def test_schema_name_may_contain_token_word_but_no_value_is_emitted(self) -> None:
        body = 'var h=n(91953);(0,h.getTldHost)(this.config.customApiToken.host,this.tld,h.TLD_MARK);'
        result = probe.analyze_body(body)
        self.assertEqual(result["hostConfigPath"], ["this", "config", "customApiToken", "host"])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertIn("customApiToken", encoded)
        self.assertNotIn("OAuth ", encoded)

    def test_ordinary_string_is_never_part_of_output(self) -> None:
        body = 'var h=n(91953);const q="DO_NOT_EMIT";(0,h.getTldHost)(q,this.tld,h.TLD_MARK);'
        encoded = json.dumps(probe.analyze_body(body), ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)


if __name__ == "__main__":
    unittest.main()
