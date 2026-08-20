from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import httpx

from musicark.providers.yandex_upload_transport import (
    YANDEX_DIRECT_UPLOAD_URL,
    YandexDirectUploadSlot,
    YandexDirectUploadTransport,
    YandexUploadHttpError,
    YandexUploadProtocolError,
)


class _Response:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Client:
    def __init__(self, factory, kwargs) -> None:
        self.factory = factory
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        record = {"url": url, "client": dict(self.kwargs), **kwargs}
        files = kwargs.get("files")
        if isinstance(files, dict) and "file" in files:
            record["multipart_name"] = "file"
            record["filename"] = files["file"][0]
        self.factory.calls.append(record)
        outcome = self.factory.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _ClientFactory:
    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []
        self.client_kwargs = []

    def __call__(self, **kwargs):
        self.client_kwargs.append(dict(kwargs))
        return _Client(self, kwargs)


class ProductionTransportTests(unittest.TestCase):
    def test_stage1_uses_verified_endpoint_exact_params_and_filename_only(self):
        factory = _ClientFactory(
            _Response(
                200,
                {
                    "post-target": "https://upload.music.yandex.net/a",
                    "poll-result": "https://poll.music.yandex.net/b",
                    "ugc-track-id": "ugc-1",
                },
            )
        )
        transport = YandexDirectUploadTransport(client_factory=factory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Artist - Track.mp3"
            slot = transport.prepare_upload(uid="42", playlist_kind="7", file_path=path)

        self.assertEqual(1, len(factory.calls))
        request = factory.calls[0]
        self.assertEqual(YANDEX_DIRECT_UPLOAD_URL, request["url"])
        self.assertEqual(
            {"uid": "42", "playlist-id": "42:7", "path": "Artist - Track.mp3"},
            request["params"],
        )
        self.assertNotIn(str(path.parent), request["params"]["path"])
        self.assertNotIn("visibility", request["params"])
        self.assertNotIn("headers", request)
        self.assertEqual("ugc-1", slot.ugc_track_id)

    def test_httpx_profile_is_fail_closed_for_both_stages(self):
        factory = _ClientFactory(
            _Response(
                200,
                {
                    "post-target": "https://upload.yandex.net/a",
                    "poll-result": "https://poll.yandex.net/b",
                    "ugc-track-id": "ugc",
                },
            ),
            _Response(201),
        )
        transport = YandexDirectUploadTransport(client_factory=factory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"mp3")
            slot = transport.prepare_upload(uid="1", playlist_kind="2", file_path=path)
            transfer = transport.upload_file(slot, path)

        self.assertEqual(201, transfer.status_code)
        self.assertEqual(2, len(factory.client_kwargs))
        for kwargs in factory.client_kwargs:
            self.assertIs(kwargs["http1"], True)
            self.assertIs(kwargs["http2"], True)
            self.assertIs(kwargs["trust_env"], False)
            self.assertIs(kwargs["follow_redirects"], False)
            self.assertGreater(kwargs["timeout"], 0)
        self.assertEqual("file", factory.calls[1]["multipart_name"])
        self.assertEqual("track.mp3", factory.calls[1]["filename"])
        self.assertNotIn("headers", factory.calls[1])

    def test_stage2_target_validation_rejects_non_yandex_http_and_userinfo(self):
        rejected = (
            "https://example.com/upload",
            "https://yandex.net.evil.example/upload",
            "http://upload.yandex.net/upload",
            "https://user:pass@upload.yandex.net/upload",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(YandexUploadProtocolError):
                    YandexDirectUploadTransport.validate_post_target(value)

        for value in (
            "https://upload.yandex.ru/path",
            "https://storage.music.yandex.net/path?signature=x",
            "https://upload.yandex.com/path",
        ):
            with self.subTest(value=value):
                self.assertEqual(value, YandexDirectUploadTransport.validate_post_target(value))

    def test_stage1_http_failure_does_not_expose_body(self):
        factory = _ClientFactory(_Response(403, {"secret": "raw-body"}))
        transport = YandexDirectUploadTransport(client_factory=factory)
        with self.assertRaises(YandexUploadHttpError) as raised:
            transport.prepare_upload(uid="1", playlist_kind="2", file_path=Path("track.mp3"))
        self.assertEqual(403, raised.exception.status_code)
        self.assertNotIn("raw-body", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))
        self.assertEqual(1, len(factory.calls))

    def test_stage2_requires_http_201_and_never_retries(self):
        factory = _ClientFactory(_Response(500))
        transport = YandexDirectUploadTransport(client_factory=factory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"mp3")
            slot = YandexDirectUploadSlot(
                post_target="https://upload.yandex.net/a",
                poll_result=None,
                ugc_track_id="1",
                status_code=200,
            )
            with self.assertRaises(YandexUploadHttpError) as raised:
                transport.upload_file(slot, path)
        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual(1, len(factory.calls))

    def test_stage2_network_failure_is_single_attempt(self):
        factory = _ClientFactory(httpx.ReadError("socket reset"))
        transport = YandexDirectUploadTransport(client_factory=factory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"mp3")
            slot = YandexDirectUploadSlot(
                post_target="https://upload.yandex.net/a",
                poll_result=None,
                ugc_track_id="1",
                status_code=200,
            )
            with self.assertRaisesRegex(Exception, "stage2"):
                transport.upload_file(slot, path)
        self.assertEqual(1, len(factory.calls))


if __name__ == "__main__":
    unittest.main()
