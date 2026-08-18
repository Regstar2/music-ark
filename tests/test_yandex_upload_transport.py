"""Offline tests for the isolated Yandex UGC upload transport PoC."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from musicark.providers.yandex_upload_transport import (
    YandexUploadProtocolError,
    YandexUploadSlot,
    YandexUploadStage1UnavailableError,
    YandexUploadTransport,
)


class _FakeStage1Requester:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post_upload_url(self, params):
        self.calls.append(dict(params))
        return self.payload


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, content_type="application/json"):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"Content-Type": content_type}

    def json(self):
        return self._payload


class YandexUploadTransportTests(unittest.TestCase):
    def test_default_stage1_fails_closed_before_request(self) -> None:
        transport = YandexUploadTransport()
        self.assertFalse(transport.stage1_available)
        with self.assertRaisesRegex(YandexUploadStage1UnavailableError, "BLOCKED"):
            transport.prepare_upload(uid=1, playlist_id=2, visibility=None, path="owned.mp3")

    def test_prepare_params_keep_recovered_query_bindings(self) -> None:
        params = YandexUploadTransport.build_prepare_params(
            uid="100",
            playlist_id="playlist-uuid",
            visibility="private",
            path=r"C:\Music\owned.mp3",
        )
        self.assertEqual(
            params,
            {
                "uid": "100",
                "playlist-id": "playlist-uuid",
                "visibility": "private",
                "path": r"C:\Music\owned.mp3",
            },
        )

    def test_injected_stage1_requester_can_validate_recovered_contract_offline(self) -> None:
        requester = _FakeStage1Requester({"url": "https://upload.example.test/signed?opaque=value"})
        transport = YandexUploadTransport(requester)
        slot = transport.prepare_upload(
            uid="100",
            playlist_id="playlist-uuid",
            visibility="private",
            path=r"C:\Music\owned.mp3",
        )
        self.assertTrue(slot.upload_url.startswith("https://upload.example.test/"))
        self.assertEqual(
            requester.calls,
            [{
                "uid": "100",
                "playlist-id": "playlist-uuid",
                "visibility": "private",
                "path": r"C:\Music\owned.mp3",
            }],
        )
        self.assertNotIn("upload.example.test", str(slot.response_shape))
        self.assertNotIn("opaque", str(slot.response_shape))

    def test_prepare_upload_rejects_missing_url_contract(self) -> None:
        transport = YandexUploadTransport(_FakeStage1Requester({"unexpected": True}))
        with self.assertRaisesRegex(YandexUploadProtocolError, "no usable HTTP"):
            transport.prepare_upload(uid=1, playlist_id=2, visibility=None, path="owned.mp3")

    def test_dynamic_upload_posts_only_multipart_file_without_yandex_headers(self) -> None:
        transport = YandexUploadTransport()
        slot = YandexUploadSlot(
            upload_url="https://upload.example.test/signed",
            response_shape={"type": "object"},
        )
        observed = {}

        def fake_post(url, **kwargs):
            observed["url"] = url
            observed["kwargs"] = kwargs
            files = kwargs["files"]
            self.assertEqual(set(files), {"file"})
            filename, stream = files["file"]
            self.assertEqual(filename, "owned.mp3")
            self.assertEqual(stream.read(), b"audio")
            stream.seek(0)
            return _FakeResponse(payload={"trackId": "ugc-123"})

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            with patch("musicark.providers.yandex_upload_transport.requests.post", side_effect=fake_post):
                result = transport.upload_file(slot, file_path)

        self.assertEqual(observed["url"], slot.upload_url)
        self.assertNotIn("headers", observed["kwargs"])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.track_id, "ugc-123")

    def test_dynamic_upload_rejects_non_success_status(self) -> None:
        transport = YandexUploadTransport()
        slot = YandexUploadSlot(
            upload_url="https://upload.example.test/signed",
            response_shape={"type": "object"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            with patch(
                "musicark.providers.yandex_upload_transport.requests.post",
                return_value=_FakeResponse(status_code=403, payload={"error": "denied"}),
            ):
                with self.assertRaisesRegex(YandexUploadProtocolError, "HTTP 403"):
                    transport.upload_file(slot, file_path)


if __name__ == "__main__":
    unittest.main()
