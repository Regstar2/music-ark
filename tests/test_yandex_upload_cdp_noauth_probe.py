"""Offline tests for the no-Authorization Chromium stage-one differential probe."""

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

_TOOL = _TOOLS / "yandex_upload_cdp_noauth_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_noauth_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadCdpNoauthProbeTests(unittest.TestCase):
    def test_expression_omits_authorization_and_secret_token(self) -> None:
        expression = probe._expression(  # noqa: SLF001
            endpoint="https://api.music.yandex.net/loader/upload-url?uid=redacted",
            oauth_token="super-secret-oauth",
        )
        self.assertNotIn("Authorization", expression)
        self.assertNotIn("super-secret-oauth", expression)
        self.assertIn("X-Yandex-Music-Client", expression)
        self.assertIn("credentials: 'omit'", expression)
        self.assertIn("method: 'POST'", expression)

    def test_run_never_reads_real_saved_oauth_and_rewrites_auth_source(self) -> None:
        args = argparse.Namespace(stage1_base_url="https://api.music.yandex.net")
        original_expression = probe.base._expression  # noqa: SLF001
        original_saved_token = probe.base.live._saved_token  # noqa: SLF001

        def fake_detail_run(_args):
            token = probe.base.live._saved_token(None)  # noqa: SLF001
            self.assertEqual(token, probe._UNUSED_TOKEN_SENTINEL)  # noqa: SLF001
            expression = probe.base._expression(  # noqa: SLF001
                endpoint="https://api.music.yandex.net/loader/upload-url?uid=redacted",
                oauth_token=token,
            )
            self.assertNotIn("Authorization", expression)
            return (
                {
                    "format": "old",
                    "stage1": {"authorizationSource": "musicark-saved-oauth"},
                    "probe": {},
                    "safety": {},
                },
                3,
            )

        with mock.patch.object(probe.detail, "run", side_effect=fake_detail_run):
            payload, code = probe.run(args)

        self.assertEqual(code, 3)
        self.assertEqual(payload["format"], "musicark-yandex-upload-cdp-noauth-differential-v1")
        self.assertEqual(payload["stage1"]["authorizationSource"], "none")
        self.assertTrue(payload["stage1"]["authorizationHeaderIntentionallyOmitted"])
        self.assertEqual(payload["probe"]["differentialVariable"], "authorization-header-omitted")
        self.assertFalse(payload["safety"]["musicark_saved_oauth_read"])
        self.assertFalse(payload["safety"]["authorization_header_sent"])
        self.assertIs(probe.base._expression, original_expression)  # noqa: SLF001
        self.assertIs(probe.base.live._saved_token, original_saved_token)  # noqa: SLF001

    def test_parser_exposes_no_token_or_cookie_inputs(self) -> None:
        parser = probe.base.build_parser()
        destinations = {action.dest for action in parser._actions}  # noqa: SLF001
        self.assertNotIn("token", destinations)
        self.assertNotIn("cookie", destinations)
        self.assertNotIn("authorization", destinations)


if __name__ == "__main__":
    unittest.main()
