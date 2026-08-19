"""Offline tests for the direct-Python recovered Stage1 contract probe."""

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

_TOOL = _TOOLS / "yandex_upload_python_composite_stage1_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_python_composite_stage1_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class _FakeResponse:
    status_code = 200
    http_version = "HTTP/2"
    headers = {"content-type": "application/json"}

    def json(self):
        return {
            "post-target": "https://signed.example.invalid/secret",
            "poll-result": "https://poll.example.invalid/secret",
            "ugc-track-id": "secret-track-id",
        }


class YandexUploadPythonCompositeStage1ProbeTests(unittest.TestCase):
    @staticmethod
    def _args() -> argparse.Namespace:
        return argparse.Namespace(
            base_dir=None,
            stage1_base_url="https://api.music.yandex.net",
            file="owned.mp3",
            playlist_kind="1055",
            transport="http2",
            client_profile="desktop",
            ignore_env=True,
            timeout=30.0,
            confirm_owned_file=True,
            confirm_prepare=True,
        )

    def test_headers_never_include_authorization_or_cookie(self) -> None:
        bare = probe._headers("bare")  # noqa: SLF001
        desktop = probe._headers("desktop")  # noqa: SLF001
        for headers in (bare, desktop):
            lower = {key.lower() for key in headers}
            self.assertNotIn("authorization", lower)
            self.assertNotIn("cookie", lower)
        self.assertEqual(desktop["X-Yandex-Music-Client"], "YandexMusicDesktopApp")

    def test_parser_exposes_no_token_cookie_session_or_raw_playlist_id(self) -> None:
        parser = probe.build_parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        forbidden = {"--token", "--oauth", "--cookie", "--session", "--playlist-id", "--authorization"}
        self.assertTrue(option_strings.isdisjoint(forbidden))

    def test_cached_context_forces_kind_only_and_does_not_require_uuid(self) -> None:
        args = self._args()
        captured: dict[str, object] = {}

        def fake_context(context_args, base_dir):  # noqa: ANN001, ANN202
            captured["playlist_id_source"] = context_args.playlist_id_source
            captured["base_dir"] = base_dir
            return probe.cdp_base._CachedStage1Context(  # noqa: SLF001
                file_path=Path("owned.mp3"),
                uid="123456",
                playlist_id="1055",
                playlist_id_source="kind",
                playlist_id_fallback=False,
                observed_visibility="public",
            )

        with mock.patch.object(probe.cdp_base, "_cached_stage1_context", side_effect=fake_context):
            context = probe._cached_context(args, None)  # noqa: SLF001
        self.assertEqual(captured["playlist_id_source"], "kind")
        self.assertEqual(context.uid, "123456")

    def test_run_sends_exact_composite_formula_and_filename_once_without_auth(self) -> None:
        args = self._args()
        context = probe.cdp_base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("C:/music/owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility="public",
        )
        captured: dict[str, object] = {}

        def fake_post(endpoint, *, params, headers, transport, trust_env, timeout):  # noqa: ANN001, ANN202
            captured.update(
                endpoint=endpoint,
                params=dict(params),
                headers=dict(headers),
                transport=transport,
                trust_env=trust_env,
                timeout=timeout,
            )
            return _FakeResponse()

        with (
            mock.patch.object(probe.live, "_require_research_opt_in"),
            mock.patch.object(probe, "_cached_context", return_value=context),
            mock.patch.object(probe, "_post_once", side_effect=fake_post) as post,
            mock.patch.object(probe.live, "_file_summary", return_value={"name": "owned.mp3", "extension": ".mp3", "size": 1}),
        ):
            payload, code = probe.run(args)

        self.assertEqual(post.call_count, 1)
        self.assertEqual(captured["endpoint"], "https://api.music.yandex.net/loader/upload-url")
        self.assertEqual(
            captured["params"],
            {"uid": "123456", "playlist-id": "123456:1055", "path": "owned.mp3"},
        )
        header_names = {key.lower() for key in captured["headers"]}
        self.assertNotIn("authorization", header_names)
        self.assertNotIn("cookie", header_names)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "upload_url_obtained")
        self.assertEqual(payload["diagnosis"], "direct-python-stage1-confirmed")
        self.assertTrue(payload["stage1"]["uploadUrlPresent"])
        self.assertFalse(payload["safety"]["credential_store_read"])
        self.assertFalse(payload["safety"]["audio_bytes_sent"])

        serialized = __import__("json").dumps(payload, ensure_ascii=False)
        self.assertNotIn("123456:1055", serialized)
        self.assertNotIn("signed.example.invalid", serialized)
        self.assertNotIn("secret-track-id", serialized)

    def test_network_failure_keeps_only_exception_classes(self) -> None:
        args = self._args()
        context = probe.cdp_base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility=None,
        )
        error = probe.httpx.RemoteProtocolError("secret URL and token must not survive")
        with (
            mock.patch.object(probe.live, "_require_research_opt_in"),
            mock.patch.object(probe, "_cached_context", return_value=context),
            mock.patch.object(probe, "_post_once", side_effect=error),
            mock.patch.object(probe.live, "_file_summary", return_value={"name": "owned.mp3", "extension": ".mp3", "size": 1}),
        ):
            payload, code = probe.run(args)

        self.assertEqual(code, 3)
        self.assertEqual(payload["diagnosis"], "python-network-path-failed")
        self.assertIn("RemoteProtocolError", payload["stage1"]["transportFailureClasses"])
        self.assertNotIn("secret URL", str(payload))
        self.assertFalse(payload["safety"]["authorization_header_sent"])

    def test_invalid_non_yandex_base_url_is_rejected_before_post(self) -> None:
        args = self._args()
        args.stage1_base_url = "https://example.com"
        context = probe.cdp_base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility=None,
        )
        with (
            mock.patch.object(probe.live, "_require_research_opt_in"),
            mock.patch.object(probe, "_cached_context", return_value=context),
            mock.patch.object(probe, "_post_once") as post,
        ):
            with self.assertRaises(probe.YandexUploadProtocolError):
                probe.run(args)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
