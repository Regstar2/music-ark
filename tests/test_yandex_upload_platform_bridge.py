from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from musicark.platform_bridge import run_action


class _Result:
    def to_dict(self):
        return {
            "status": "verified",
            "localFileId": 7,
            "playlistKind": "11",
            "trackId": "ugc-1",
            "stage1HttpStatus": 200,
            "stage2HttpStatus": 201,
            "readBackVerified": True,
            "readBackAttempts": 1,
            "errorCode": None,
            "safeMessage": "verified",
        }


class PlatformBridgeUploadTests(unittest.TestCase):
    def test_production_action_requires_exact_four_field_payload(self):
        service = Mock()
        service.upload_track.return_value = _Result()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("musicark.platform_bridge.YandexSingleTrackUploadService", return_value=service):
                result = run_action(
                    "yandex_upload_track",
                    base_dir=Path(tmp),
                    payload={
                        "local_file_id": 7,
                        "playlist_kind": "11",
                        "confirm": True,
                        "rights_confirmed": True,
                    },
                )
        self.assertEqual("verified", result["status"])
        service.upload_track.assert_called_once_with(
            local_file_id=7,
            playlist_kind="11",
            confirm=True,
            rights_confirmed=True,
        )

    def test_path_and_extra_fields_are_rejected_before_service_call(self):
        service = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("musicark.platform_bridge.YandexSingleTrackUploadService", return_value=service):
                with self.assertRaises(ValueError):
                    run_action(
                        "yandex_upload_track",
                        base_dir=Path(tmp),
                        payload={
                            "local_file_id": 7,
                            "playlist_kind": "11",
                            "confirm": True,
                            "rights_confirmed": True,
                            "path": r"C:\private\track.mp3",
                        },
                    )
        service.upload_track.assert_not_called()

    def test_false_confirmations_are_forwarded_to_fail_closed_service(self):
        service = Mock()
        service.upload_track.return_value = _Result()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("musicark.platform_bridge.YandexSingleTrackUploadService", return_value=service):
                run_action(
                    "yandex_upload_track",
                    base_dir=Path(tmp),
                    payload={
                        "local_file_id": 7,
                        "playlist_kind": "11",
                        "confirm": False,
                        "rights_confirmed": False,
                    },
                )
        service.upload_track.assert_called_once_with(
            local_file_id=7,
            playlist_kind="11",
            confirm=False,
            rights_confirmed=False,
        )

    def test_legacy_experimental_action_does_not_invoke_production_service(self):
        production = Mock()
        legacy_result = {"status": "blocked", "mutationAttempted": False}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("musicark.platform_bridge.YandexSingleTrackUploadService", production), patch(
                "musicark.platform_bridge.execute_experimental_yandex_upload",
                return_value=legacy_result,
            ) as legacy:
                result = run_action(
                    "experimental_yandex_upload",
                    base_dir=Path(tmp),
                    payload={"confirm": True},
                )
        self.assertEqual(legacy_result, result)
        legacy.assert_called_once()
        production.assert_not_called()


if __name__ == "__main__":
    unittest.main()
