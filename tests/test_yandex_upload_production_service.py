from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.providers.yandex_upload_transport import (
    YandexDirectUploadSlot,
    YandexUploadHttpError,
    YandexUploadNetworkError,
)
from musicark.storage.audit_log import AuditEvent
from musicark.sync.models import SyncOperationType, SyncScopeType
from musicark.sync.planner import SyncPlanner, _PlanInput
from musicark.upload.bridge import UploadBridgeRequestError, _read_upload_payload
from musicark.upload.yandex_service import YandexSingleTrackUploadService, YandexUploadStatus


class _LocalRepository:
    def __init__(self, row) -> None:
        self.row = row

    def get_track(self, track_id):
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

    def get_playlist(self, external_id):
        self.playlist_calls += 1
        if external_id != "7":
            raise RuntimeError("playlist unavailable")
        ids = ["old"]
        if self.playlist_calls > 1 and self.readbacks:
            ids = self.readbacks.pop(0)
        playlist = ProviderPlaylist(
            provider_id="yandex_music",
            external_id="7",
            title="Mine",
            track_external_ids=tuple(ids),
            owner_name="User",
            raw_data={"owner": {"uid": self.owner_uid}},
        )
        return playlist, [_track(value) for value in ids]


class _Transport:
    def __init__(self, *, stage1=None, stage2=None, ugc_track_id="ugc-1") -> None:
        self.stage1_calls = 0
        self.stage2_calls = 0
        self.stage1 = stage1
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
        if isinstance(self.stage1, BaseException):
            raise self.stage1
        return self.slot

    def upload_file(self, slot, file_path):
        self.stage2_calls += 1
        if isinstance(self.stage2, BaseException):
            raise self.stage2
        return type("Transfer", (), {"status_code": 201})()


def _track(external_id: str) -> ProviderTrack:
    return ProviderTrack(
        provider_id="yandex_music",
        external_id=external_id,
        title=external_id,
        artists=("Artist",),
    )


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
        tx = transport or _Transport()
        service = YandexSingleTrackUploadService(
            provider=provider or _Provider(readbacks=[["old", "ugc-1"]]),
            transport=tx,
            local_repository=local,
            audit_repository=audit,
            read_back_attempts=3,
            read_back_interval_seconds=0,
            sleeper=lambda _: None,
        )
        return service, local, audit, tx

    def test_preflight_rejects_non_mp3_missing_empty_and_invalid_id_before_stage1(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flac = root / "track.flac"
            flac.write_bytes(b"audio")
            service, _, _, tx = self._service(flac, extension=".flac")
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual(YandexUploadStatus.UNSUPPORTED_FORMAT, result.status)
            self.assertEqual(0, tx.stage1_calls)

            missing = root / "missing.mp3"
            service, _, _, tx = self._service(missing)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("missing_file", result.error_code)
            self.assertEqual(0, tx.stage1_calls)

            empty = root / "empty.mp3"
            empty.write_bytes(b"")
            service, _, _, tx = self._service(empty)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("empty_file", result.error_code)
            self.assertEqual(0, tx.stage1_calls)

            valid = root / "valid.mp3"
            valid.write_bytes(b"x")
            service, local, _, tx = self._service(valid)
            local.row = None
            result = service.upload_track(local_file_id=99, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("invalid_local_file_id", result.error_code)
            self.assertEqual(0, tx.stage1_calls)

    def test_confirm_rights_auth_and_ownership_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            for confirm, rights, code in (
                (False, True, "confirmation_required"),
                (True, False, "rights_confirmation_required"),
            ):
                service, _, _, tx = self._service(path)
                result = service.upload_track(
                    local_file_id=10,
                    playlist_kind="7",
                    confirm=confirm,
                    rights_confirmed=rights,
                )
                self.assertEqual(code, result.error_code)
                self.assertEqual(0, tx.stage1_calls)

            service, _, _, tx = self._service(path, provider=_Provider(uid="", owner_uid=""))
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("auth_required", result.error_code)
            self.assertEqual(0, tx.stage1_calls)

            service, _, _, tx = self._service(path, provider=_Provider(uid="42", owner_uid="99"))
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual("playlist_not_owned", result.error_code)
            self.assertEqual(0, tx.stage1_calls)

    def test_successful_stage1_stage2_and_readback_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            tx = _Transport()
            service, _, audit, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old", "ugc-1"]]),
                transport=tx,
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.VERIFIED, result.status)
        self.assertTrue(result.read_back_verified)
        self.assertEqual(200, result.stage1_http_status)
        self.assertEqual(201, result.stage2_http_status)
        self.assertEqual(1, tx.stage1_calls)
        self.assertEqual(1, tx.stage2_calls)
        self.assertEqual(["upload_started", "upload_verified"], [event.event_type for event in audit.events])
        self.assertEqual("track.mp3", tx.prepare_kwargs["file_path"].name)
        verified_details = json.loads(audit.events[-1].details or "{}")
        self.assertEqual(200, verified_details["stage1HttpStatus"])
        self.assertEqual(201, verified_details["stage2HttpStatus"])
        self.assertEqual(1, verified_details["readBackAttempts"])

    def test_stage2_network_exception_verified_by_readback_never_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            tx = _Transport(stage2=YandexUploadNetworkError("stage2", "ReadError"))
            service, _, _, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old", "ugc-1"]]),
                transport=tx,
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.VERIFIED, result.status)
        self.assertEqual(1, tx.stage1_calls)
        self.assertEqual(1, tx.stage2_calls)

    def test_stage2_network_exception_without_readback_is_delivery_unknown_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            tx = _Transport(stage2=YandexUploadNetworkError("stage2", "ReadError"))
            service, _, audit, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old"], ["old"], ["old"]]),
                transport=tx,
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.DELIVERY_UNKNOWN, result.status)
        self.assertEqual(3, result.read_back_attempts)
        self.assertEqual(1, tx.stage1_calls)
        self.assertEqual(1, tx.stage2_calls)
        self.assertEqual("upload_delivery_unknown", audit.events[-1].event_type)

    def test_ambiguous_readback_is_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            service, _, _, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old", "new-a", "new-b"]]),
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.AMBIGUOUS, result.status)
        self.assertFalse(result.read_back_verified)

    def test_stage1_and_stage2_http_failures_are_typed_and_single_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            tx = _Transport(stage1=YandexUploadHttpError("stage1", 403))
            service, _, audit, _ = self._service(path, transport=tx)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual(YandexUploadStatus.STAGE1_FAILED, result.status)
            self.assertEqual(403, result.stage1_http_status)
            self.assertEqual(1, tx.stage1_calls)
            self.assertEqual(0, tx.stage2_calls)
            self.assertEqual(403, json.loads(audit.events[-1].details or "{}")["stage1HttpStatus"])

            tx = _Transport(stage2=YandexUploadHttpError("stage2", 400))
            service, _, audit, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old"], ["old"], ["old"]]),
                transport=tx,
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
            self.assertEqual(YandexUploadStatus.STAGE2_HTTP_FAILED, result.status)
            self.assertEqual(400, result.stage2_http_status)
            self.assertEqual(3, result.read_back_attempts)
            self.assertEqual(1, tx.stage2_calls)
            failure_details = json.loads(audit.events[-1].details or "{}")
            self.assertEqual(200, failure_details["stage1HttpStatus"])
            self.assertEqual(400, failure_details["stage2HttpStatus"])
            self.assertEqual(3, failure_details["readBackAttempts"])

    def test_stage2_http_failure_verified_by_readback_never_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            path.write_bytes(b"audio")
            tx = _Transport(stage2=YandexUploadHttpError("stage2", 500))
            service, _, audit, _ = self._service(
                path,
                provider=_Provider(readbacks=[["old", "ugc-1"]]),
                transport=tx,
            )
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        self.assertEqual(YandexUploadStatus.VERIFIED, result.status)
        self.assertTrue(result.read_back_verified)
        self.assertEqual(500, result.stage2_http_status)
        self.assertEqual(1, result.read_back_attempts)
        self.assertEqual(1, tx.stage2_calls)
        self.assertEqual("upload_verified", audit.events[-1].event_type)
        details = json.loads(audit.events[-1].details or "{}")
        self.assertEqual(500, details["stage2HttpStatus"])

    def test_result_and_audit_never_serialize_uid_path_or_signed_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-name.mp3"
            path.write_bytes(b"audio")
            service, _, audit, _ = self._service(path)
            result = service.upload_track(local_file_id=10, playlist_kind="7", confirm=True, rights_confirmed=True)
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        audit_text = "\n".join(event.details or "" for event in audit.events)
        for forbidden in (
            "upload.music.yandex.net",
            "poll.music.yandex.net",
            "token=secret",
            "42:7",
            str(path),
        ):
            self.assertNotIn(forbidden, serialized)
            self.assertNotIn(forbidden, audit_text)


class BridgeAndCapabilityRegressionTests(unittest.TestCase):
    def test_structured_bridge_requires_exact_four_field_payload(self):
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

    def test_provider_capabilities_advertise_manual_upload(self):
        capabilities = YandexMusicProvider().capabilities
        self.assertTrue(capabilities.can_upload_tracks)
        self.assertTrue(capabilities.supports_user_uploads)

    def test_sync_planner_does_not_generate_upload_operation(self):
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
