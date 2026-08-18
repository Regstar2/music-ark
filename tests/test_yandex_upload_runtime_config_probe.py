"""Tests for the source-free Yandex desktop runtime-config probe."""

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

_TOOL = _TOOLS / "yandex_upload_runtime_config_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_config_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRuntimeConfigProbeTests(unittest.TestCase):
    def test_null_custom_overrides_are_reported_without_values(self) -> None:
        records = probe._records('{"customApiPrefixUrl":null,"customApiToken":null}')  # noqa: SLF001
        self.assertIn({"key": "customApiPrefixUrl", "kind": "null"}, records)
        self.assertIn({"key": "customApiToken", "kind": "null"}, records)

    def test_sensitive_custom_token_value_is_never_emitted(self) -> None:
        records = probe._records('customApiToken:"SUPER_SECRET_TOKEN"')  # noqa: SLF001
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertIn("redacted-sensitive-value", encoded)
        self.assertNotIn("SUPER_SECRET_TOKEN", encoded)

    def test_public_client_enum_is_allowlisted(self) -> None:
        records = probe._records('clientRemoteType:"YandexMusicDesktopApp"')  # noqa: SLF001
        self.assertEqual(
            records,
            [{"key": "clientRemoteType", "kind": "public-enum", "value": "YandexMusicDesktopApp"}],
        )

    def test_prefix_url_query_is_removed(self) -> None:
        records = probe._records('prefixUrl:"https://api.music.yandex.net/root?a=SECRET"')  # noqa: SLF001
        self.assertEqual(
            records,
            [{"key": "prefixUrl", "kind": "public-yandex-url", "value": "https://api.music.yandex.net/root"}],
        )

    def test_ordinary_string_is_classified_but_not_emitted(self) -> None:
        records = probe._records('customApiPrefixUrl:"DO_NOT_EMIT"')  # noqa: SLF001
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertEqual(records, [{"key": "customApiPrefixUrl", "kind": "string"}])
        self.assertNotIn("DO_NOT_EMIT", encoded)


if __name__ == "__main__":
    unittest.main()
