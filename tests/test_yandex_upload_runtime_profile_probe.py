"""Tests for the source-free Yandex desktop runtime-profile probe."""

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

_TOOL = _TOOLS / "yandex_upload_runtime_profile_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_profile_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRuntimeProfileProbeTests(unittest.TestCase):
    def test_direct_prefix_binding_keeps_only_yandex_scheme_host_path(self) -> None:
        source = 'customApiPrefixUrl:"https://api.music.yandex.net/v1/root?token=SECRET#frag"'
        bindings = probe._direct_bindings(source)  # noqa: SLF001
        self.assertEqual(
            bindings,
            [{"key": "customApiPrefixUrl", "url": "https://api.music.yandex.net/v1/root"}],
        )

    def test_anchor_record_exposes_only_public_profile_and_header_names(self) -> None:
        source = (
            'const ordinary="DO_NOT_EMIT";'
            'const secret="SUPER_SECRET";'
            'const u="https://api.music.yandex.net/loader/upload-url?x=1";'
            'const profile="YandexMusicDesktopApp";'
            'const h={"user-agent":"VALUE","authorization":"OAuth SECRET"};'
            'getApiPrefixUrl();'
        )
        urls = probe._url_occurrences(source)  # noqa: SLF001
        records = probe._anchor_records(source, urls, 1000)  # noqa: SLF001
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertIn("https://api.music.yandex.net/loader/upload-url", encoded)
        self.assertIn("YandexMusicDesktopApp", encoded)
        self.assertIn("user-agent", encoded)
        self.assertIn("authorization", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("SUPER_SECRET", encoded)
        self.assertNotIn("OAuth SECRET", encoded)

    def test_module_anchor_sets_prove_only_allowlisted_colocation(self) -> None:
        source = (
            '123:(e,t,n)=>{'
            'const ordinary="DO_NOT_EMIT";'
            'const secret="SUPER_SECRET";'
            'function getUploadUrl(){return "loader/upload-url"}'
            'function getApiPrefixUrl(){}'
            'function createHttpOptions(){}'
            'const remote="YandexMusicDesktopApp";'
            '},'
            '456:(e,t,n)=>{const x="unrelated";}'
        )
        records = probe._module_anchor_sets(source)  # noqa: SLF001
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["module_id"], "123")
        self.assertIn("loader/upload-url", records[0]["anchors"])
        self.assertIn("getUploadUrl", records[0]["anchors"])
        self.assertIn("getApiPrefixUrl", records[0]["anchors"])
        self.assertIn("createHttpOptions", records[0]["anchors"])
        self.assertIn("YandexMusicDesktopApp", records[0]["anchors"])
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("SUPER_SECRET", encoded)

    def test_non_yandex_urls_are_ignored(self) -> None:
        self.assertIsNone(probe._sanitize_yandex_url("https://example.com/api"))  # noqa: SLF001
        self.assertEqual(
            probe._sanitize_yandex_url("https://music.yandex.ru/api/test?a=b"),  # noqa: SLF001
            "https://music.yandex.ru/api/test",
        )

    def test_sensitive_url_text_is_rejected(self) -> None:
        self.assertIsNone(
            probe._sanitize_yandex_url("https://api.music.yandex.net/path/token=SECRET")  # noqa: SLF001
        )


if __name__ == "__main__":
    unittest.main()
