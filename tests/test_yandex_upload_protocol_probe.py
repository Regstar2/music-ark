"""Tests for the offline Yandex upload protocol research tool."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "yandex_upload_protocol_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_protocol_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadProtocolProbeTests(unittest.TestCase):
    def test_sanitize_url_keeps_names_and_drops_values(self) -> None:
        sanitized = probe.sanitize_url(
            "https://api.music.yandex.net/upload?sign=super-secret&playlistUuid=abc-123#fragment"
        )
        self.assertIn("sign=%3Credacted%3E", sanitized)
        self.assertIn("playlistUuid=%3Credacted%3E", sanitized)
        self.assertNotIn("super-secret", sanitized)
        self.assertNotIn("abc-123", sanitized)
        self.assertNotIn("fragment", sanitized)

    def test_har_report_exposes_shape_without_secret_values(self) -> None:
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.music.yandex.net/upload?sign=query-secret",
                            "headers": [
                                {"name": "Authorization", "value": "OAuth auth-secret"},
                                {"name": "Cookie", "value": "Session_id=cookie-secret"},
                                {"name": "Content-Type", "value": "multipart/form-data; boundary=secret-boundary"},
                            ],
                            "postData": {
                                "mimeType": "multipart/form-data",
                                "params": [
                                    {"name": "playlistUuid", "value": "private-playlist"},
                                    {"name": "file", "fileName": "private_song.mp3", "value": "raw-file-data"},
                                ],
                            },
                        },
                        "response": {
                            "status": 200,
                            "headers": [
                                {"name": "Set-Cookie", "value": "session=response-secret"},
                                {"name": "Content-Type", "value": "application/json"},
                            ],
                            "content": {
                                "mimeType": "application/json",
                                "text": json.dumps(
                                    {
                                        "track": {"id": "user-track-id", "title": "Private title"},
                                        "token": "response-token-secret",
                                    }
                                ),
                            },
                        },
                    }
                ]
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.har"
            path.write_text(json.dumps(har), encoding="utf-8")
            report = probe.sanitize_har(path)

        encoded = json.dumps(report, ensure_ascii=False)
        for secret in (
            "auth-secret",
            "cookie-secret",
            "query-secret",
            "private-playlist",
            "private_song.mp3",
            "raw-file-data",
            "response-secret",
            "user-track-id",
            "Private title",
            "response-token-secret",
            "secret-boundary",
        ):
            self.assertNotIn(secret, encoded)

        entry = report["entries"][0]
        self.assertEqual(entry["method"], "POST")
        self.assertEqual(entry["request_body"]["field_names"], ["file", "playlistUuid"])
        self.assertEqual(entry["request_body"]["files"][0]["filename"], "<redacted>.mp3")
        self.assertEqual(entry["response"]["json_shape"]["track"]["id"], "string")
        self.assertEqual(entry["response"]["json_shape"]["token"], "<redacted-field>")

    def test_binary_scan_redacts_auth_and_finds_endpoint_shape(self) -> None:
        source = (
            'const x="Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789";'
            'this.httpClient.post("/playlist/123/upload", {body:new FormData()});'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.asar"
            path.write_bytes(source)
            report = probe.scan_binary(path, keywords=("upload",), max_hits=10)

        encoded = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["hit_count"], 1)
        self.assertIn("/playlist/123/upload", encoded)
        self.assertIn("Bearer <redacted>", encoded)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz0123456789", encoded)


if __name__ == "__main__":
    unittest.main()
