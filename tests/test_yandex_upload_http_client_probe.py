"""Tests for the source-free V7 Yandex upload HTTP-client probe."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_http_client_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_http_client_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadHttpClientProbeTests(unittest.TestCase):
    def test_url_sanitizer_strips_query_and_fragment(self) -> None:
        value = probe._sanitize_url(  # noqa: SLF001
            "https://music.example.test/api/upload?token=secret&x=1#fragment"
        )
        self.assertEqual(value, "https://music.example.test/api/upload")

    def test_structural_window_emits_names_not_values(self) -> None:
        source = (
            'const api="https://api.music.yandex.net/loader/upload-url?token=SECRET";'
            'const headers={"Authorization":"OAuth SUPERSECRET",'
            '"X-Yandex-Music-Client":"DesktopSecretValue",'
            '"User-Agent":"Private Agent"};'
            'class UgcUploadHttpClient{getUploadUrl(){return api}}'
        )
        start = source.index("UgcUploadHttpClient")
        data = probe._nearby_structural_data(source, start, start + 19, 500)  # noqa: SLF001
        self.assertIn("https://api.music.yandex.net/loader/upload-url", data["nearby_urls"])
        self.assertIn("authorization", data["nearby_header_names"])
        self.assertIn("x-yandex-music-client", data["nearby_header_names"])
        self.assertIn("user-agent", data["nearby_header_names"])
        encoded = repr(data)
        self.assertNotIn("SUPERSECRET", encoded)
        self.assertNotIn("DesktopSecretValue", encoded)
        self.assertNotIn("Private Agent", encoded)
        self.assertNotIn("token=SECRET", encoded)


if __name__ == "__main__":
    unittest.main()
