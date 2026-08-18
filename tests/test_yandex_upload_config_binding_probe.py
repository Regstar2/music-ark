"""Tests for the source-free V8 Yandex upload config-binding probe."""

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

_TOOL = _TOOLS / "yandex_upload_config_binding_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_config_binding_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadConfigBindingProbeTests(unittest.TestCase):
    def test_extracts_config_relationships_without_secret_values(self) -> None:
        source = (
            'const cfg={'
            'customApiPrefixUrl:getApiPrefixUrl(runtime),'
            'customApiToken:SUPER_SECRET_TOKEN,'
            'clientRemoteType:YandexMusicDesktopApp};'
            'const client=new UgcUploadHttpClient(createHttpOptions({'
            'prefixUrl:cfg.customApiPrefixUrl,'
            'headers:createRequestHeaders(cfg.customApiToken),'
            'clientRemoteType:cfg.clientRemoteType,'
            'excludeHeaders:false}));'
        )

        bindings = probe._all_interesting_object_bindings(source)  # noqa: SLF001
        calls = probe._call_relations(source)  # noqa: SLF001
        encoded = json.dumps({"bindings": bindings, "calls": calls}, ensure_ascii=False)

        self.assertNotIn("SUPER_SECRET_TOKEN", encoded)
        self.assertIn(
            {"path": "customApiPrefixUrl", "value": {"kind": "call", "callee": "getApiPrefixUrl"}},
            bindings,
        )
        self.assertIn(
            {"path": "customApiToken", "value": {"kind": "redacted-sensitive-value"}},
            bindings,
        )
        self.assertIn(
            {"path": "clientRemoteType", "value": {"kind": "protocol-enum", "name": "YandexMusicDesktopApp"}},
            bindings,
        )
        self.assertIn(
            {"path": "prefixUrl", "value": {"kind": "member", "value": "cfg.customApiPrefixUrl"}},
            bindings,
        )
        self.assertTrue(any(item["callee"] == "UgcUploadHttpClient" for item in calls))
        self.assertTrue(any(item["callee"] == "createHttpOptions" for item in calls))
        self.assertTrue(any(item["callee"] == "createRequestHeaders" for item in calls))

    def test_sensitive_members_are_named_but_values_are_not_exposed(self) -> None:
        kind = probe._expression_kind("cfg.customApiToken")  # noqa: SLF001
        self.assertEqual(kind, {"kind": "sensitive-member", "name": "customApiToken"})

    def test_urls_are_sanitized(self) -> None:
        kind = probe._expression_kind("'https://example.test/api?token=secret#x'")  # noqa: SLF001
        self.assertEqual(kind, {"kind": "url", "value": "https://example.test/api"})


if __name__ == "__main__":
    unittest.main()
