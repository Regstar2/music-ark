"""Offline tests for the renderer-language Chromium stage-one differential."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_language_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_language_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadCdpLanguageProbeTests(unittest.TestCase):
    def test_expression_adds_renderer_language_without_authorization(self) -> None:
        expression = probe._expression(  # noqa: SLF001
            endpoint="https://api.music.yandex.net/loader/upload-url?uid=redacted",
            oauth_token="super-secret-oauth",
        )
        self.assertIn("'Accept-Language': language", expression)
        self.assertIn("navigator.language", expression)
        self.assertIn("X-Yandex-Music-Client", expression)
        self.assertIn("credentials: 'omit'", expression)
        self.assertNotIn("Authorization", expression)
        self.assertNotIn("super-secret-oauth", expression)

    def test_run_changes_only_language_marker_and_restores_noauth_expression(self) -> None:
        args = argparse.Namespace(stage1_base_url="https://api.music.yandex.net")
        original_expression = probe.noauth._expression  # noqa: SLF001

        def fake_noauth_run(_args):
            expression = probe.noauth._expression(  # noqa: SLF001
                endpoint="https://api.music.yandex.net/loader/upload-url?uid=redacted",
                oauth_token="unused-secret",
            )
            self.assertIn("'Accept-Language': language", expression)
            self.assertNotIn("Authorization", expression)
            self.assertNotIn("unused-secret", expression)
            return (
                {
                    "format": "old",
                    "stage1": {
                        "authorizationSource": "none",
                        "authorizationHeaderIntentionallyOmitted": True,
                    },
                    "probe": {"differentialVariable": "authorization-header-omitted"},
                    "safety": {
                        "musicark_saved_oauth_read": False,
                        "authorization_header_sent": False,
                    },
                },
                3,
            )

        with mock.patch.object(probe.noauth, "run", side_effect=fake_noauth_run):
            payload, code = probe.run(args)

        self.assertEqual(code, 3)
        self.assertEqual(payload["format"], "musicark-yandex-upload-cdp-language-differential-v1")
        self.assertEqual(payload["stage1"]["authorizationSource"], "none")
        self.assertEqual(
            payload["stage1"]["acceptLanguageSource"],
            "electron-renderer-navigator.language",
        )
        self.assertEqual(payload["probe"]["differentialVariable"], "accept-language-from-renderer")
        self.assertFalse(payload["safety"]["accept_language_value_included"])
        self.assertIs(probe.noauth._expression, original_expression)  # noqa: SLF001

    def test_parser_exposes_no_secret_inputs(self) -> None:
        parser = probe.noauth.base.build_parser()
        destinations = {action.dest for action in parser._actions}  # noqa: SLF001
        self.assertNotIn("token", destinations)
        self.assertNotIn("cookie", destinations)
        self.assertNotIn("authorization", destinations)


if __name__ == "__main__":
    unittest.main()
