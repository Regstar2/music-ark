"""Offline safety and orchestration tests for the direct-Python live upload PoC."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_python_composite_live_poc.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_python_composite_live_poc", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
poc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(poc)


class _FakeStage2Response:
    status_code = 200
    http_version = "HTTP/2"
    headers = {"Content-Type": "application/json"}

    def json(self):
        return {"trackId": "new-track-id", "opaque": "must-not-survive"}


class YandexUploadPythonCompositeLivePocTests(unittest.TestCase):
    @staticmethod
    def _args() -> argparse.Namespace:
        return argparse.Namespace(
            base_dir=None,
            stage1_base_url="https://api.music.yandex.net",
            file="owned.mp3",
            playlist_kind="1055",
            transport="http2",
            stage2_transport="http2",
            client_profile="desktop",
            ignore_env=True,
            timeout=30.0,
            transfer_timeout=120.0,
            readback_attempts=3,
            readback_delay=0.0,
            confirm_owned_file=True,
            confirm_upload=True,
        )

    def test_parser_exposes_no_token_cookie_session_or_raw_playlist_id(self) -> None:
        parser = poc.build_parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        forbidden = {"--token", "--oauth", "--cookie", "--session", "--playlist-id", "--authorization"}
        self.assertTrue(option_strings.isdisjoint(forbidden))
        self.assertIn("--stage2-transport", option_strings)

    def test_live_env_is_required_before_upload_context(self) -> None:
        args = self._args()
        with (
            mock.patch.object(poc.live, "_require_research_opt_in"),
            mock.patch.dict(os.environ, {"MUSICARK_YANDEX_UPLOAD_LIVE": ""}, clear=False),
        ):
            with self.assertRaises(poc.YandexUploadProtocolError):
                poc._require_live_confirmation(args, None)  # noqa: SLF001

    def test_dynamic_target_requires_https_yandex_host(self) -> None:
        allowed = poc._validate_dynamic_upload_target(  # noqa: SLF001
            "https://music-loader-production-1.music.yandex.ru/upload?opaque=signed"
        )
        self.assertTrue(allowed.startswith("https://music-loader-production-1.music.yandex.ru/"))
        for value in (
            "http://music.yandex.ru/upload",
            "https://example.com/upload",
            "https://user:pass@music.yandex.ru/upload",
        ):
            with self.assertRaises(poc.YandexUploadProtocolError):
                poc._validate_dynamic_upload_target(value)  # noqa: SLF001

    def test_authenticated_uid_mismatch_fails_closed(self) -> None:
        fake_playlist = type("Playlist", (), {"uid": "654321"})()
        with (
            mock.patch.object(poc.live, "_build_client", return_value=object()),
            mock.patch.object(poc.live, "_resolve_playlist", return_value=fake_playlist),
            mock.patch.object(poc.live, "_playlist_track_ids") as track_ids,
        ):
            with self.assertRaises(poc.YandexUploadProtocolError):
                poc._authenticated_target(  # noqa: SLF001
                    base_dir=None,
                    playlist_kind="1055",
                    expected_uid="123456",
                )
        track_ids.assert_not_called()

    def test_stage2_httpx_honors_ignore_env_without_fallback(self) -> None:
        slot = poc.YandexUploadSlot(
            upload_url="https://music-loader-production-1.music.yandex.ru/upload?opaque=signed-secret",
            response_shape={"type": "object"},
        )
        path = Path("owned.mp3")
        fake_stream = mock.MagicMock()
        fake_context = mock.MagicMock()
        fake_context.__enter__.return_value = fake_stream
        fake_context.__exit__.return_value = False
        fake_client = mock.MagicMock()
        fake_client.__enter__.return_value.post.return_value = _FakeStage2Response()
        fake_client.__exit__.return_value = False

        with (
            mock.patch.object(Path, "is_file", return_value=True),
            mock.patch.object(Path, "stat", return_value=type("S", (), {"st_size": 123})()),
            mock.patch.object(Path, "open", return_value=fake_context),
            mock.patch.object(poc.httpx, "Client", return_value=fake_client) as client_cls,
            mock.patch.object(poc.requests, "post") as requests_post,
        ):
            response = poc._stage2_post_once(  # noqa: SLF001
                slot,
                path,
                transport="http2",
                trust_env=False,
                timeout=120.0,
            )

        self.assertEqual(response.status_code, 200)
        kwargs = client_cls.call_args.kwargs
        self.assertFalse(kwargs["trust_env"])
        self.assertTrue(kwargs["http1"])
        self.assertTrue(kwargs["http2"])
        self.assertFalse(kwargs["follow_redirects"])
        self.assertEqual(fake_client.__enter__.return_value.post.call_count, 1)
        requests_post.assert_not_called()

    def test_run_sends_one_stage2_then_verifies_readback(self) -> None:
        args = self._args()
        context = poc.stage1.cdp_base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("C:/music/owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility="public",
        )
        slot = poc.YandexUploadSlot(
            upload_url="https://music-loader-production-1.music.yandex.ru/upload?opaque=signed-secret",
            response_shape={"type": "object", "keys": {"post-target": {"type": "string"}}},
            poll_url="https://api.music.yandex.net/poll?opaque=signed-secret",
            track_id="new-track-id",
        )

        with (
            mock.patch.object(poc, "_require_live_confirmation"),
            mock.patch.object(poc.stage1, "_cached_context", return_value=context),
            mock.patch.object(
                poc,
                "_authenticated_target",
                return_value=(object(), object(), {"old-track-id"}, "123456"),
            ),
            mock.patch.object(poc, "_stage1_slot", return_value=(slot, 200, "HTTP/1.1")) as stage1_call,
            mock.patch.object(poc, "_stage2_post_once", return_value=_FakeStage2Response()) as stage2_post,
            mock.patch.object(poc.live, "_refresh_playlist", return_value=object()) as refresh,
            mock.patch.object(poc.live, "_playlist_track_ids", return_value={"old-track-id", "new-track-id"}),
            mock.patch.object(
                poc.live,
                "_file_summary",
                return_value={"name": "owned.mp3", "extension": ".mp3", "size": 123},
            ),
        ):
            payload, code = poc.run(args)

        self.assertEqual(stage1_call.call_count, 1)
        self.assertEqual(stage2_post.call_count, 1)
        self.assertFalse(stage2_post.call_args.kwargs["trust_env"])
        self.assertEqual(stage2_post.call_args.kwargs["transport"], "http2")
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["stage1"]["httpStatus"], 200)
        self.assertEqual(payload["stage2"]["httpStatus"], 200)
        self.assertEqual(payload["stage2"]["httpVersion"], "HTTP/2")
        self.assertEqual(payload["stage2"]["multipartField"], "file")
        self.assertTrue(payload["playlist"]["authenticatedUidMatch"])
        self.assertTrue(payload["readBack"]["verified"])
        self.assertEqual(payload["readBack"]["verifiedTrackId"], "new-track-id")
        self.assertFalse(payload["safety"]["stage1_authorization_header_sent"])
        self.assertFalse(payload["safety"]["stage2_authorization_header_sent"])
        self.assertTrue(payload["safety"]["audio_delivery_confirmed"])

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("123456:1055", serialized)
        self.assertNotIn("signed-secret", serialized)
        self.assertNotIn("music-loader-production-1", serialized)
        self.assertNotIn("must-not-survive", serialized)

    def test_stage2_network_failure_is_sanitized_and_skips_readback(self) -> None:
        args = self._args()
        context = poc.stage1.cdp_base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("C:/music/owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility="public",
        )
        slot = poc.YandexUploadSlot(
            upload_url="https://music-loader-production-1.music.yandex.ru/upload?opaque=signed-secret",
            response_shape={"type": "object", "keys": {"post-target": {"type": "string"}}},
            track_id="reserved-track-id",
        )
        error = poc.httpx.RemoteProtocolError("signed-secret must not survive")

        with (
            mock.patch.object(poc, "_require_live_confirmation"),
            mock.patch.object(poc.stage1, "_cached_context", return_value=context),
            mock.patch.object(
                poc,
                "_authenticated_target",
                return_value=(object(), object(), {"old-track-id"}, "123456"),
            ),
            mock.patch.object(poc, "_stage1_slot", return_value=(slot, 200, "HTTP/1.1")),
            mock.patch.object(poc, "_stage2_post_once", side_effect=error) as stage2_post,
            mock.patch.object(poc.live, "_refresh_playlist") as refresh,
            mock.patch.object(
                poc.live,
                "_file_summary",
                return_value={"name": "owned.mp3", "extension": ".mp3", "size": 123},
            ),
        ):
            payload, code = poc.run(args)

        self.assertEqual(stage2_post.call_count, 1)
        refresh.assert_not_called()
        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "stage2_network_failed")
        self.assertEqual(payload["stage1"]["httpStatus"], 200)
        self.assertFalse(payload["stage2"]["httpResponseReceived"])
        self.assertIn("RemoteProtocolError", payload["stage2"]["transportFailureClasses"])
        self.assertFalse(payload["network"]["readBackSent"])
        self.assertTrue(payload["safety"]["audio_submission_attempted"])
        self.assertFalse(payload["safety"]["audio_delivery_confirmed"])
        self.assertFalse(payload["probe"]["automaticTransportFallback"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("signed-secret", serialized)
        self.assertNotIn("reserved-track-id", serialized)


if __name__ == "__main__":
    unittest.main()
