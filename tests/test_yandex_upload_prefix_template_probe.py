"""Offline tests for the proven stage-one prefix-template probe."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_prefix_template_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_prefix_template_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPrefixTemplateProbeTests(unittest.TestCase):
    def test_template_allows_yandex_tld_placeholder(self) -> None:
        self.assertEqual(
            probe._safe_template("https://api.music.yandex.{tld}"),  # noqa: SLF001
            "https://api.music.yandex.{tld}",
        )

    def test_template_rejects_query_secret_and_non_yandex(self) -> None:
        self.assertIsNone(probe._safe_template("https://api.music.yandex.ru/a?token=SECRET"))  # noqa: SLF001
        self.assertIsNone(probe._safe_template("https://example.com/{tld}"))  # noqa: SLF001

    def test_module_scan_does_not_emit_unrelated_strings(self) -> None:
        body = 'const a="DO_NOT_EMIT",b="https://api.music.yandex.{tld}",c="https://mc.yandex.ru/watch/";'
        self.assertEqual(
            probe._templates(body),  # noqa: SLF001
            ["https://api.music.yandex.{tld}", "https://mc.yandex.ru/watch/"],
        )


if __name__ == "__main__":
    unittest.main()
