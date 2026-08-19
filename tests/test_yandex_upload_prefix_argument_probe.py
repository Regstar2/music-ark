"""Offline tests for exact getTldHost argument normalization."""

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

_TOOL = _TOOLS / "yandex_upload_prefix_argument_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_argument_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixArgumentProbeTests(unittest.TestCase):
    def test_wrapped_call_normalizes_three_arguments(self) -> None:
        body = 'var h=n(91953),p=n(32732);const t=x;const v=(0,h.getTldHost)(p,t,h.TLD_MARK);'
        result = probe._find_call(body)  # noqa: SLF001
        assert result is not None
        self.assertEqual(result["argumentCount"], 3)
        self.assertEqual(result["arguments"][0]["normalized"], ["m32732"])
        self.assertEqual(result["arguments"][2]["normalized"], ["m91953.TLD_MARK"])

    def test_direct_call_normalizes_imported_member(self) -> None:
        body = 'var h=n(91953),p=n(32732);h.getTldHost(p.mZ,t,h.TLD_MARK);'
        result = probe._find_call(body)  # noqa: SLF001
        assert result is not None
        self.assertEqual(result["arguments"][0]["normalized"], ["m32732.mZ"])

    def test_arbitrary_string_value_is_reduced_to_shape(self) -> None:
        body = 'var h=n(91953);h.getTldHost("DO_NOT_EMIT",t,h.TLD_MARK);'
        result = probe._find_call(body)  # noqa: SLF001
        assert result is not None
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertIn("<string>", encoded)


if __name__ == "__main__":
    unittest.main()
