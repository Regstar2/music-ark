"""Offline tests for the official-desktop stage-one fingerprint collector."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import urlencode
from unittest import mock


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_desktop_stage1_fingerprint.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_desktop_stage1_fingerprint", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadDesktopStage1FingerprintTests(unittest.TestCase):
    def test_query_fingerprint_classifies_known_context_without_values(self) -> None:
        file_path = Path(r"C:\Music\Owned Track.mp3")
        url = "https://api.music.yandex.net/loader/upload-url?" + urlencode(
            {
                "uid": "123456",
                "playlist-id": "playlist-uuid-secret",
                "path": str(file_path),
                "visibility": "public",
            }
        )

        payload = probe._query_fingerprint(  # noqa: SLF001
            url,
            uid="123456",
            playlist_uuid="playlist-uuid-secret",
            playlist_kind="1055",
            file_path=file_path,
            visibility="public",
        )

        self.assertEqual(payload["queryNames"], ["path", "playlist-id", "uid", "visibility"])
        self.assertEqual(payload["queryValueClasses"]["uid"], "matches-cached-uid")
        self.assertEqual(payload["queryValueClasses"]["playlist-id"], "matches-cached-uuid")
        self.assertEqual(payload["queryValueClasses"]["path"], "matches-full-path")
        self.assertEqual(payload["queryValueClasses"]["visibility"], "matches-cached-visibility")
        serialized = json.dumps(payload)
        self.assertNotIn("123456", serialized)
        self.assertNotIn("playlist-uuid-secret", serialized)
        self.assertNotIn("Owned Track.mp3", serialized)

    def test_query_fingerprint_distinguishes_kind_and_filename(self) -> None:
        file_path = Path(r"C:\Music\Owned Track.mp3")
        url = "https://api.music.yandex.net/loader/upload-url?" + urlencode(
            {"uid": "different", "playlist-id": "1055", "path": file_path.name}
        )

        payload = probe._query_fingerprint(  # noqa: SLF001
            url,
            uid="123456",
            playlist_uuid="playlist-uuid-secret",
            playlist_kind="1055",
            file_path=file_path,
            visibility="public",
        )

        self.assertEqual(payload["queryValueClasses"]["uid"], "other")
        self.assertEqual(payload["queryValueClasses"]["playlist-id"], "matches-kind")
        self.assertEqual(payload["queryValueClasses"]["path"], "matches-file-name")
        self.assertEqual(payload["queryValueClasses"]["visibility"], "missing")

    def test_collector_correlates_wire_extra_info_without_secret_values(self) -> None:
        file_path = Path(r"C:\Music\Owned Track.mp3")
        collector = probe._FingerprintCollector(  # noqa: SLF001
            uid="123456",
            playlist_uuid="playlist-uuid-secret",
            playlist_kind="1055",
            file_path=file_path,
            visibility="public",
        )
        request_id = "request-id-secret"
        url = "https://api.music.yandex.net/loader/upload-url?" + urlencode(
            {"uid": "123456", "playlist-id": "playlist-uuid-secret", "path": file_path.name}
        )

        # ExtraInfo may arrive before requestWillBeSent; the collector must still correlate it.
        collector.observe(
            {
                "method": "Network.requestWillBeSentExtraInfo",
                "params": {
                    "requestId": request_id,
                    "headers": {
                        "Authorization": "OAuth token-secret",
                        "Cookie": "session-secret",
                        "Accept-Language": "ru-RU",
                        "X-Yandex-Music-Client": "YandexMusicDesktopApp",
                        "X-Retry-Count": "0",
                        "X-Request-Id": "request-value-secret",
                    },
                },
            }
        )
        collector.observe(
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": request_id,
                    "type": "Fetch",
                    "request": {
                        "method": "POST",
                        "url": url,
                        "hasPostData": False,
                        "headers": {
                            "Accept": "application/json",
                            "Authorization": "OAuth token-secret",
                            "X-Yandex-Music-Client": "YandexMusicDesktopApp",
                        },
                    },
                },
            }
        )
        collector.observe(
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": request_id,
                    "response": {
                        "status": 200,
                        "protocol": "h2",
                        "headers": {"Content-Type": "application/json"},
                    },
                },
            }
        )
        collector.observe(
            {
                "method": "Network.responseReceivedExtraInfo",
                "params": {
                    "requestId": request_id,
                    "statusCode": 200,
                    "headers": {"Server": "secret-server-value"},
                },
            }
        )
        collector.observe(
            {"method": "Network.loadingFinished", "params": {"requestId": request_id}}
        )

        summary = collector.summary()
        fingerprint = summary["successfulFingerprint"]
        self.assertEqual(summary["successfulStage1Posts"], 1)
        self.assertEqual(fingerprint["responseProtocol"], "h2")
        self.assertEqual(fingerprint["queryValueClasses"]["playlist-id"], "matches-cached-uuid")
        self.assertEqual(fingerprint["queryValueClasses"]["path"], "matches-file-name")
        self.assertTrue(fingerprint["headerPresence"]["authorization"])
        self.assertTrue(fingerprint["headerPresence"]["cookie"])
        self.assertTrue(fingerprint["headerPresence"]["x-retry-count"])
        self.assertIn("accept-language", fingerprint["wireOnlyHeaderNames"])
        self.assertTrue(fingerprint["loadingFinished"])

        serialized = json.dumps(summary, ensure_ascii=False)
        for forbidden in (
            request_id,
            "token-secret",
            "session-secret",
            "request-value-secret",
            "secret-server-value",
            "playlist-uuid-secret",
            "123456",
            str(file_path),
        ):
            self.assertNotIn(forbidden, serialized)

    def test_parser_exposes_only_observation_inputs(self) -> None:
        parser = probe.build_parser()
        destinations = {action.dest for action in parser._actions}  # noqa: SLF001
        self.assertNotIn("token", destinations)
        self.assertNotIn("cookie", destinations)
        self.assertNotIn("authorization", destinations)
        self.assertNotIn("stage1_base_url", destinations)
        self.assertNotIn("confirm_prepare", destinations)
        self.assertIn("confirm_desktop_upload", destinations)

    def test_confirmation_blocks_before_context_or_desktop(self) -> None:
        args = argparse.Namespace(
            confirm_owned_file=True,
            confirm_desktop_upload=False,
            duration=30.0,
        )
        with mock.patch.object(probe.uuid_probe, "_uuid_context") as context:  # noqa: SLF001
            with self.assertRaisesRegex(Exception, "confirm-desktop-upload"):
                probe.run(args)
        context.assert_not_called()

    def test_safe_protocol_and_failure_code_emit_enum_like_values_only(self) -> None:
        self.assertEqual(probe._safe_protocol("h2"), "h2")  # noqa: SLF001
        self.assertEqual(probe._safe_protocol("HTTP/1.1"), "HTTP/1.1")  # noqa: SLF001
        self.assertEqual(probe._safe_protocol("h2 secret value"), "unknown")  # noqa: SLF001
        self.assertEqual(probe._safe_net_error("net::ERR_HTTP2_PROTOCOL_ERROR"), "NET::ERR_HTTP2_PROTOCOL_ERROR")  # noqa: SLF001
        self.assertEqual(probe._safe_net_error("arbitrary failure detail"), "unknown")  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
