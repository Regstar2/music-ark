"""Tests for the source-free V13 Yandex upload destructure probe."""

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

_TOOL = _TOOLS / "yandex_upload_destructure_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_destructure_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadDestructureProbeTests(unittest.TestCase):
    def test_object_destructure_maps_export_local_to_safe_property(self) -> None:
        source = (
            'n.d(e,{Xc:()=>A,RG:()=>B});'
            'const {UgcUploadHttpClient:A,ResourceHttpClient:B}=factory();'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        self.assertEqual(len(record["object_destructures"]), 1)
        pairs = record["object_destructures"][0]["pairs"]
        self.assertIn({"property": "UgcUploadHttpClient", "local": "A"}, pairs)
        self.assertIn({"property": "ResourceHttpClient", "local": "B"}, pairs)

    def test_parameter_object_destructure_is_classified(self) -> None:
        source = (
            'n.d(e,{Xc:()=>A,RG:()=>B});'
            'function f({UgcUploadHttpClient:A,other:C},B){return 1}'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        encoded = json.dumps(record["parameter_bindings"], ensure_ascii=False)
        self.assertIn("UgcUploadHttpClient", encoded)
        self.assertIn('"local": "A"', encoded)
        self.assertIn('"local": "B"', encoded)

    def test_secret_and_ordinary_values_are_not_emitted(self) -> None:
        source = (
            'n.d(e,{Xc:()=>A,RG:()=>B});'
            'const {client:A,other:B}=make("SUPER_SECRET_TOKEN","ORDINARY_VALUE");'
        )
        record = probe._provider_record("chunk.js", source, ["Xc", "RG"])  # noqa: SLF001
        encoded = json.dumps(record, ensure_ascii=False)
        self.assertNotIn("SUPER_SECRET_TOKEN", encoded)
        self.assertNotIn("ORDINARY_VALUE", encoded)


if __name__ == "__main__":
    unittest.main()
