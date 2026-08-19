from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.providers.yandex_upload_transport import (
    YANDEX_DIRECT_UPLOAD_URL,
    YandexDirectUploadSlot,
    YandexDirectUploadTransport,
    YandexUploadHttpError,
    YandexUploadNetworkError,
    YandexUploadProtocolError,
)
from musicark.storage.audit_log import AuditEvent
from musicark.sync.models import SyncOperationType, SyncScopeType
from musicark.sync.planner import SyncPlanner, _PlanInput
from musicark.upload.bridge import UploadBridgeRequestError, _read_upload_payload
from musicark.upload.yandex_service import YandexSingleTrackUploadService, YandexUploadStatus


class _Response:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _Client:
    def __init__(self, owner, kwargs) -> None:
        self.owner = owner
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        record = {"url": url, **kwargs, "client": dict(self.kwargs)}
        files = kwargs.get("files")
        if isinstance(files, dict) and "file" in files:
            record["multipart_name"] = "file"
            record["filename"] = files["file"][0]
        self.owner.calls.append(record)
        outcome = self.owner.outcomes.pop(0)
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


class _LocalRepository:
    def __init__(self, row) -> None:
        self.row = row
        self.calls = 0

    def get_track(self, track_id):
        self.calls += 1
        return self.row if self.row and self.row.get("id") == track_id else None


class _AuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)


class _Provider:
    def __init__(self, *, uid="42", owner_uid="42", readbacks=None) -> None:
        self.uid = uid
        self.owner_uid = owner_uid
        self.readbacks = list(readbacks or [])
        self.playlist_calls = 0

    def auth_check(self):
        return {"providerUserId": self.uid, "displayName": "User"}

    def _playlist(self):
        return ProviderPlaylist(
            provider_id="yandex_music",
            external_id="7",
            title="Mine",
            track_external_ids=(),
            owner_name="User",
            raw_data={"owner": {"uid": self.owner_uid}},
        )

    def get_playlist(self, external_id):
        self.playlist_calls += 1
        if external_id != "7":
            raise RuntimeError("missing")
        if self.playlist_calls == 1:
            ids = ["old"]
        elif self.readbacks:
            ids = self.readbacks.pop(0)
        else:
            ids = ["old"]
        return self._playlist(), [_provider_track(value) for value in ids]


class _Transport:
    def __init__(self, *, stage2=None, ugc_track_id="ugc-1") -> None:
        self.stage1_calls = 0
        self.stage2_calls = 0
        self.stage2 = stage2
        self.slot = YandexDirectUploadSlot(
            post_target="https://upload.music.yandex.net/signed?token=secret",
            poll_result="https://poll.music.yandex.net/secret",
            ugc_track_id=ugc_track_id,
            status_code=200,
        )

    def prepare_upload(self, **kwargs):
        self.stage1_calls += 1
        self.prepare_kwargs = kwargs
        return self.slot

    def upload_file(self, slot, file_path):
        self.stage2_calls += 1
        if isinstance(self.stage2, BaseException):
            raise self.stage2
        return type("Transfer", (), {"status_code": 201})()


def _provider_track(external_id: str) -> ProviderTrack:
    return ProviderTrack(
        provider_id="yandex_music",
        external_id=external_id,
        title=external_id,
        artists=("Artist",),
    )


class ProductionTransportTests(unittest.TestCase):
    def test_stage1_uses_verified_endpoint_exact_params_and_filename(self):
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
        slot = transport.prepare_upload(
            uid="42",
            playlist_kind="7",
            file_path=Path(r"C:\Secret\Artist\Track.mp3"),
        )
        self.assertEqual(YANDEX_DIRECT_UPLOAD_URL, factory.calls[0]["url"])
        self.assertEqual(
            {"uid": "42", "playlist-id": "42:7", "path": "C:\\Secret\\Artist\\Track.mp3"},
            factory.calls[0]["params"],
        )
        # pathlib on non-Windows treats backslashes as filename characters; the
        # portable production invariant is that only Path.name is used.
        self.assertEqual(Path(r"C:\Secret\Artist\Track.mp3").name, factory.calls[0]["params"]["path"])
        self.assertNotIn("visibility", factory.calls[0]["params"])
        self.assertNotIn("headers", factory.calls[0])
        self.assertEqual("ugc-1", slot.ugc_track_id)
        self.assertEqual(1, len(factory.calls))

    def test_httpx_profile_is_fail_closed_for_both_stages(self):
        factory = _ClientFactory(
            _Response(200, {"post-target": "https://upload.yandex.net/a", "ugc-track-id": "ugc"}),
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
        self.assertEqual("file", factory.calls[1]["multipart_name"])
        self.assertEqual("track.mp3", factory.calls[1]["filename"])
        self.assertNotIn("headers", factory.calls[1])

    def test_stage2_rejects_arbitrary_https_host_and_userinfo(self):
        for value in (
            "https://example.com/upload",
            "http://upload.yandex.net/upload",
            "https://user:pass@upload.yandex.net/upload",
        ):
            with self.subTest(value=value):
                with self.assertRaises(YandexUploadProtocolError):
                    YandexDirectUploadTransport.validate_post_target(value)

    def test_stage1_non_200_is_typed_http_failure_without_body(self):
        factory = _ClientFactory(_Response(403, {"secret": "body"}))
        transport = YandexDirectUploadTransport(client_factory=factory)
        with self.assertRaises(YandexUploadHttpError) as raised:
            transport.prepare_upload(uid="1", playlist_kind="2", file_path=Path("track.mp3"))
        self.assertEqual(403, raised.exception.status_code)
        self.assertNotIn("secret", str(raised.exception))

    def test_stage2_201_only_success_and_no_retry(self):
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
            with self.assertRaises(YandexUploadHttpError):
                transport.upload_file(slot, path)
        self.assertEqual(1, len(factory.calls))


class ProductionServiceTests(unittest.TestCase):
    def _service(self, path: Path, *, provider=None, transport=None, extension=".mp3"):
        local = _LocalRepository(
            {
                "id": 10,
                "path": str(path),
                "fileName": path.name,
                "extension": extension,
                "fileSize": path.stat().st_size if path.exists() else 0,
            }
        )
        audit = _AuditRepository()
        transport = transport or _Transport()
        service = YandexSingleTrackUploadService(
            provider=provider or _Provider(readbacks=[["old", "ugc-1"]]),
            transport=transport,
            local_repository=local,
            audit_repository=audit,
            read_back_attempts=3,
            read_back_interval_seconds=0,
            sleeper=lambda _: None,
        )
        return service, local, audit, transport

    def test_non_mp3_fails_before_stage1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.flac"
            path.write_bytes(b"audio")
            service, _, _, transport = self._service(path, extension=".flac")
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.UNSUPPORTED_FORMAT, result.status)
        self.assertEqual(0, transport.stage1_calls)

    def test_missing_empty_and_invalid_local_file_fail_before_stage1(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.mp3"
            service, _, _, transport = self._service(missing)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("missing_file", result.error_code)
            self.assertEqual(0, transport.stage1_calls)

            empty = Path(tmp) / "empty.mp3"
            empty.write_bytes(b"")
            service, _, _, transport = self._service(empty)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("empty_file", result.error_code)
            self.assertEqual(0, transport.stage1_calls)

            valid = Path(tmp) / "valid.mp3"
            valid.write_bytes(b"x")
            service, local, _, transport = self._service(valid)
            local.row = None
            result = service.upload_track(local_file_id=99, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("invalid_local_file_id", result.error_code)
            self.assertEqual(0, transport.stage1_calls)

    def test_confirm_and_rights_are_mandatory_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            for confirm, rights, code in (
                (False, True, "confirmation_required"),
                (True, False, "rights_confirmation_required"),
            ):
                service, _, _, transport = self._service(path)
                result = service.upload_track(
                    local_file_id=10,
                    playlist_kind="7",
                    confirm=confirm,
                    rights_confirmed=rights,
                )
                self.assertEqual(code, result.error_code)
                self.assertEqual(0, transport.stage1_calls)

    def test_auth_and_playlist_ownership_fail_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            service, _, _, transport = self._service(path, provider=_Provider(uid="", owner_uid=""))
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("auth_required", result.error_code)
            self.assertEqual(0, transport.stage1_calls)

            service, _, _, transport = self._service(path, provider=_Provider(uid="42", owner_uid="99"))
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("playlist_not_owned", result.error_code)
            self.assertEqual(0, transport.stage1_calls)

    def test_successful_upload_and_readback_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            transport = _Transport()
            provider = _Provider(readbacks=[["old", "ugc-1"]])
            service, _, audit, _ = self._service(path, provider=provider, transport=transport)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.VERIFIED, result.status)
        self.assertEqual(200, result.stage1_http_status)
        self.assertEqual(201, result.stage2_http_status)
        self.assertTrue(result.read_back_verified)
        self.assertEqual(1, transport.stage1_calls)
        self.assertEqual(1, transport.stage2_calls)
        self.assertEqual(["upload_started", "upload_verified"], [event.event_type for event in audit.events])

    def test_network_exception_then_readback_verified_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            transport = _Transport(stage2=YandexUploadNetworkError("stage2", "ReadError"))
            provider = _Provider(readbacks=[["old", "ugc-1"]])
            service, _, _, _ = self._service(path, provider=provider, transport=transport)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.VERIFIED, result.status)
        self.assertEqual(1, transport.stage1_calls)
        self.assertEqual(1, transport.stage2_calls)

    def test_network_exception_without_readback_is_delivery_unknown_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            transport = _Transport(stage2=YandexUploadNetworkError("stage2", "ReadError"))
            provider = _Provider(readbacks=[["old"], ["old"], ["old"]])
            service, _, audit, _ = self._service(path, provider=provider, transport=transport)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.DELIVERY_UNKNOWN, result.status)
        self.assertEqual(1, transport.stage1_calls)
        self.assertEqual(1, transport.stage2_calls)
        self.assertEqual(3, result.read_back_attempts)
        self.assertEqual("upload_delivery_unknown", audit.events[-1].event_type)

    def test_ambiguous_readback_is_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            provider = _Provider(readbacks=[["old", "new-a", "new-b"]])
            service, _, _, _ = self._service(path, provider=provider)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.AMBIGUOUS, result.status)
        self.assertFalse(result.read_back_verified)

    def test_stage2_http_failure_is_typed_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            transport = _Transport(stage2=YandexUploadHttpError("stage2", 400))
            service, _, _, _ = self._service(path, transport=transport)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.STAGE2_HTTP_FAILED, result.status)
        self.assertEqual(400, result.stage2_http_status)
        self.assertEqual(1, transport.stage2_calls)

    def test_serialized_result_and_audit_do_not_expose_signed_urls_uid_or_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-name.mp3"
            path.write_bytes(b"audio")
            service, _, audit, _ = self._service(path)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        audit_text = "\n".join(event.details or "" for event in audit.events)
        for forbidden in ("upload.music.yandex.net", "poll.music.yandex.net", "42:7", str(path), "token=secret"):
            self.assertNotIn(forbidden, serialized)
            self.assertNotIn(forbidden, audit_text)


class BridgeAndCapabilityRegressionTests(unittest.TestCase):
    def test_structured_bridge_requires_exact_shape(self):
        valid = {
            "local_file_id": 10,
            "playlist_kind": "7",
            "confirm": True,
            "rights_confirmed": True,
        }
        with patch.dict("os.environ", {"MUSICARK_YANDEX_UPLOAD_PAYLOAD": json.dumps(valid)}, clear=False):
            self.assertEqual(valid, _read_upload_payload())
        invalid = {**valid, "path": "C:/secret.mp3"}
        with patch.dict("os.environ", {"MUSICARK_YANDEX_UPLOAD_PAYLOAD": json.dumps(invalid)}, clear=False):
            with self.assertRaises(UploadBridgeRequestError):
                _read_upload_payload()

    def test_provider_advertises_manual_upload_capability(self):
        capabilities = YandexMusicProvider().capabilities
        self.assertTrue(capabilities.can_upload_tracks)
        self.assertTrue(capabilities.supports_user_uploads)

    def test_sync_planner_still_does_not_generate_upload_candidate(self):
        planner = SyncPlanner.__new__(SyncPlanner)
        planner._local_only_rows = lambda data: []
        data = _PlanInput(
            scope_type=SyncScopeType.ALL,
            scope_id=None,
            collection_id="",
            target_root_id=None,
            target_folder=None,
            tracks=[
                {
                    "providerId": "yandex_music",
                    "externalId": "123",
                    "coverageStatus": "missing",
                    "userAction": "unreviewed",
                    "variantStatus": "not_checked",
                    "provider": {"title": "Track", "artists": ["Artist"]},
                }
            ],
            local_fingerprint="local",
            active_downloads={},
        )
        plan = planner._plan_from_inputs(data, dry_run=True)
        self.assertNotIn(
            SyncOperationType.UPLOAD_CANDIDATE,
            [operation.operation_type for operation in plan.operations],
        )


if __name__ == "__main__":
    unittest.main()
