"""Offline tests for the isolated Yandex UGC upload transport PoC."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
import requests

from musicark.providers.yandex_upload_transport import (
    YandexOAuthStage1Requester,
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
    def __init__(
        self,
        status_code=200,
        payload=None,
        content_type="application/json",
        text="",
        http_version="HTTP/2",
    ):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"Content-Type": content_type}
        self.text = text
        self.http_version = http_version

    def json(self):
        return self._payload


class _FakeHttpxClient:
    def __init__(self, response, observed, **kwargs):
        self._response = response
        self._observed = observed
        self._observed["client_kwargs"] = dict(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self._observed["url"] = url
        self._observed["post_kwargs"] = kwargs
        return self._response


class YandexUploadTransportTests(unittest.TestCase):
    def test_oauth_stage1_requester_requires_explicit_https_yandex_prefix(self) -> None:
        for invalid in (
            "",
            "http://api.music.yandex.net",
            "https://example.com",
            "https://user:pass@api.music.yandex.net",
            "https://api.music.yandex.net?token=secret",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(YandexUploadProtocolError):
                    YandexOAuthStage1Requester(base_url=invalid, oauth_token="owned-oauth")

    def test_oauth_stage1_requester_rejects_unknown_transport_and_profile(self) -> None:
        with self.assertRaises(YandexUploadProtocolError):
            YandexOAuthStage1Requester(
                base_url="https://api.music.yandex.net",
                oauth_token="owned-oauth",
                transport_mode="magic",
            )
        with self.assertRaises(YandexUploadProtocolError):
            YandexOAuthStage1Requester(
                base_url="https://api.music.yandex.net",
                oauth_token="owned-oauth",
                client_profile="guess",
            )

    def test_oauth_stage1_requester_posts_exact_recovered_endpoint_once(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://music.yandex.ru/api",
            oauth_token="owned-oauth-secret",
            timeout_seconds=9,
        )
        observed = []

        def fake_post(url, **kwargs):
            observed.append((url, kwargs))
            return _FakeResponse(payload={"post-target": "https://upload.example.test/signed"})

        with patch("musicark.providers.yandex_upload_transport.requests.post", side_effect=fake_post):
            payload = requester.post_upload_url({"uid": "1", "playlist-id": "2", "path": "owned.mp3"})

        self.assertEqual(payload, {"post-target": "https://upload.example.test/signed"})
        self.assertEqual(len(observed), 1)
        url, kwargs = observed[0]
        self.assertEqual(url, "https://music.yandex.ru/api/loader/upload-url")
        self.assertEqual(kwargs["params"], {"uid": "1", "playlist-id": "2", "path": "owned.mp3"})
        self.assertEqual(
            kwargs["headers"],
            {
                "Accept": "application/json",
                "Authorization": "OAuth owned-oauth-secret",
            },
        )
        self.assertEqual(kwargs["timeout"], 9.0)
        self.assertNotIn("cookies", kwargs)

    def test_desktop_profile_adds_only_evidenced_public_client_header(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://api.music.yandex.net",
            oauth_token="owned-oauth-secret",
            client_profile="desktop",
        )
        observed = []

        def fake_post(url, **kwargs):
            observed.append(kwargs)
            return _FakeResponse(payload={"post-target": "https://upload.example.test/signed"})

        with patch("musicark.providers.yandex_upload_transport.requests.post", side_effect=fake_post):
            requester.post_upload_url({"uid": "1", "playlist-id": "2", "path": "owned.mp3"})

        headers = observed[0]["headers"]
        self.assertEqual(headers["X-Yandex-Music-Client"], "YandexMusicDesktopApp")
        self.assertEqual(set(headers), {"Accept", "Authorization", "X-Yandex-Music-Client"})
        self.assertNotIn("Cookie", headers)
        self.assertNotIn("User-Agent", headers)
        self.assertNotIn("X-Request-Id", headers)

    def test_http2_profile_uses_httpx_without_fallback(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://api.music.yandex.net",
            oauth_token="owned-oauth-secret",
            timeout_seconds=11,
            transport_mode="http2",
            client_profile="desktop",
            trust_env=False,
        )
        observed = {}
        response = _FakeResponse(payload={"post-target": "https://upload.example.test/signed"})

        def fake_client(**kwargs):
            return _FakeHttpxClient(response, observed, **kwargs)

        with patch("musicark.providers.yandex_upload_transport.httpx.Client", side_effect=fake_client):
            payload = requester.post_upload_url({"uid": "1", "playlist-id": "2", "path": "owned.mp3"})

        self.assertEqual(payload, {"post-target": "https://upload.example.test/signed"})
        self.assertEqual(observed["url"], "https://api.music.yandex.net/loader/upload-url")
        self.assertTrue(observed["client_kwargs"]["http2"])
        self.assertTrue(observed["client_kwargs"]["http1"])
        self.assertFalse(observed["client_kwargs"]["trust_env"])
        self.assertFalse(observed["client_kwargs"]["follow_redirects"])
        self.assertEqual(observed["client_kwargs"]["timeout"], 11.0)
        self.assertEqual(
            observed["post_kwargs"]["headers"]["X-Yandex-Music-Client"],
            "YandexMusicDesktopApp",
        )

    def test_http2_error_reports_profile_and_exception_kind_without_secret(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://api.music.yandex.net",
            oauth_token="do-not-leak-this-token",
            transport_mode="http2",
            client_profile="desktop",
            trust_env=False,
        )
        failure = httpx.ConnectError("sensitive transport details")
        with patch.object(requester, "_http2_post", side_effect=failure):
            with self.assertRaises(YandexUploadProtocolError) as caught:
                requester.post_upload_url({"uid": "1", "path": "sensitive-local-path.mp3"})
        message = str(caught.exception)
        self.assertIn("client=http2", message)
        self.assertIn("profile=desktop", message)
        self.assertIn("env=ignore", message)
        self.assertIn("transport=ConnectError", message)
        self.assertNotIn("do-not-leak-this-token", message)
        self.assertNotIn("sensitive transport details", message)
        self.assertNotIn("sensitive-local-path", message)

    def test_oauth_stage1_requester_error_does_not_expose_credential(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://music.yandex.ru/api",
            oauth_token="do-not-leak-this-token",
        )
        with patch(
            "musicark.providers.yandex_upload_transport.requests.post",
            return_value=_FakeResponse(status_code=403, payload={"error": "secret body"}),
        ):
            with self.assertRaises(YandexUploadProtocolError) as caught:
                requester.post_upload_url({"uid": "1"})
        self.assertIn("HTTP 403", str(caught.exception))
        self.assertNotIn("do-not-leak-this-token", str(caught.exception))
        self.assertNotIn("secret body", str(caught.exception))

    def test_oauth_stage1_transport_failure_reports_only_exception_kinds(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://api.music.yandex.net",
            oauth_token="do-not-leak-this-token",
        )
        nested = requests.exceptions.ProxyError("sensitive proxy details")
        failure = requests.exceptions.ConnectionError(nested)
        with patch(
            "musicark.providers.yandex_upload_transport.requests.post",
            side_effect=failure,
        ):
            with self.assertRaises(YandexUploadProtocolError) as caught:
                requester.post_upload_url({"uid": "1", "path": "sensitive-local-path.mp3"})
        message = str(caught.exception)
        self.assertIn("transport=ConnectionError/ProxyError", message)
        self.assertNotIn("do-not-leak-this-token", message)
        self.assertNotIn("sensitive proxy details", message)
        self.assertNotIn("sensitive-local-path", message)

    def test_default_stage1_fails_closed_before_request(self) -> None:
        transport = YandexUploadTransport()
        self.assertFalse(transport.stage1_available)
        with self.assertRaisesRegex(YandexUploadStage1UnavailableError, "BLOCKED"):
            transport.prepare_upload(uid=1, playlist_id=2, visibility=None, path="owned.mp3")

    def test_transport_exposes_only_sanitized_stage1_profile(self) -> None:
        requester = YandexOAuthStage1Requester(
            base_url="https://api.music.yandex.net",
            oauth_token="do-not-leak",
            transport_mode="http2",
            client_profile="desktop",
            trust_env=False,
        )
        transport = YandexUploadTransport(requester)
        self.assertEqual(
            transport.stage1_profile,
            {
                "transport": "http2",
                "clientProfile": "desktop",
                "trustEnv": False,
                "desktopClientHeader": True,
            },
        )
        self.assertNotIn("do-not-leak", str(transport.stage1_profile))

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

    def test_observed_stage1_response_extracts_post_target_poll_and_ugc_id(self) -> None:
        requester = _FakeStage1Requester(
            {
                "post-target": "https://upload.example.test/signed?opaque=upload",
                "poll-result": "https://upload.example.test/poll?opaque=poll",
                "ugc-track-id": "ugc-ground-truth-123",
            }
        )
        transport = YandexUploadTransport(requester)
        slot = transport.prepare_upload(
            uid="100",
            playlist_id="playlist-uuid",
            visibility=None,
            path=r"C:\Music\owned.mp3",
        )
        self.assertEqual(slot.upload_url, "https://upload.example.test/signed?opaque=upload")
        self.assertEqual(slot.poll_url, "https://upload.example.test/poll?opaque=poll")
        self.assertEqual(slot.track_id, "ugc-ground-truth-123")
        self.assertNotIn("upload.example.test", str(slot.response_shape))
        self.assertNotIn("ugc-ground-truth-123", str(slot.response_shape))
        self.assertEqual(
            set(slot.response_shape["keys"]),
            {"post-target", "poll-result", "ugc-track-id"},
        )

    def test_injected_stage1_requester_keeps_legacy_url_shape_compatible(self) -> None:
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
            return _FakeResponse(payload={"ugc-track-id": "ugc-123"})

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
