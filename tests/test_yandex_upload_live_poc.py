"""Offline tests for the explicit Yandex single-track upload PoC runner."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_live_poc.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_live_poc", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
poc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(poc)


class YandexUploadLivePocTests(unittest.TestCase):
    def test_single_new_readback_id_is_verified(self) -> None:
        result = poc._classify_readback_identity({"1", "2"}, {"1", "2", "3"}, None)  # noqa: SLF001
        self.assertTrue(result["verified"])
        self.assertEqual(result["verifiedTrackId"], "3")
        self.assertEqual(result["identitySource"], "single-readback-difference")
        self.assertFalse(result["ambiguous"])

    def test_multiple_new_ids_without_reported_identity_are_not_verified(self) -> None:
        result = poc._classify_readback_identity({"1"}, {"1", "2", "3"}, None)  # noqa: SLF001
        self.assertFalse(result["verified"])
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["newTrackIds"], ["2", "3"])

    def test_reported_track_id_resolves_multiple_readback_ids(self) -> None:
        result = poc._classify_readback_identity({"1"}, {"1", "2", "3"}, "3")  # noqa: SLF001
        self.assertTrue(result["verified"])
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["verifiedTrackId"], "3")
        self.assertEqual(result["identitySource"], "reported-track-id")

    def test_existing_reported_track_id_does_not_verify_upload(self) -> None:
        result = poc._classify_readback_identity({"1", "2"}, {"1", "2"}, "2")  # noqa: SLF001
        self.assertFalse(result["verified"])
        self.assertEqual(result["identitySource"], "not-observed")

    def test_prepare_blocks_before_credentials_or_playlist_network(self) -> None:
        args = argparse.Namespace(confirm_prepare=True)
        with patch.object(poc, "_prepare_context") as prepare_context:
            with self.assertRaisesRegex(Exception, "BLOCKED"):
                poc.run_prepare(args)
        prepare_context.assert_not_called()

    def test_upload_blocks_before_credentials_or_playlist_network(self) -> None:
        args = argparse.Namespace(confirm_upload=True)
        with patch.dict(poc.os.environ, {"MUSICARK_YANDEX_UPLOAD_LIVE": "1"}, clear=False):
            with patch.object(poc, "_prepare_context") as prepare_context:
                with self.assertRaisesRegex(Exception, "BLOCKED"):
                    poc.run_upload(args)
        prepare_context.assert_not_called()

    def test_explicit_ground_truth_base_url_enables_oauth_stage1_transport(self) -> None:
        with patch.object(poc, "_saved_token", return_value="saved-account-oauth") as saved_token:
            transport = poc._live_transport(None, "https://api.music.yandex.net")  # noqa: SLF001
        self.assertTrue(transport.stage1_available)
        saved_token.assert_called_once_with(None)

    def test_non_yandex_stage1_base_url_is_rejected_before_network(self) -> None:
        with patch.object(poc, "_saved_token", return_value="saved-account-oauth"):
            with self.assertRaisesRegex(Exception, "HTTPS Yandex"):
                poc._live_transport(None, "https://example.test")  # noqa: SLF001

    def test_prepare_matches_observed_query_without_visibility(self) -> None:
        args = argparse.Namespace(
            confirm_prepare=True,
            base_dir=None,
            stage1_base_url="https://api.music.yandex.net",
            playlist_id_source="uuid",
            path_mode="full",
        )
        transport = Mock()
        transport.prepare_upload.return_value = SimpleNamespace(
            upload_url="https://upload.example.test/signed",
            poll_url="https://upload.example.test/poll",
            track_id="ugc-1",
            response_shape={"type": "object"},
        )
        playlist = SimpleNamespace(kind=1055)
        with patch.object(poc, "_live_transport", return_value=transport), \
             patch.object(
                 poc,
                 "_prepare_context",
                 return_value=(None, playlist, Path("owned.mp3"), "100", "playlist-uuid", "private"),
             ), \
             patch.object(poc, "_file_summary", return_value={"name": "owned.mp3"}):
            result = poc.run_prepare(args)

        transport.require_stage1_profile.assert_called_once_with()
        transport.prepare_upload.assert_called_once_with(
            uid="100",
            playlist_id="playlist-uuid",
            visibility=None,
            path="owned.mp3",
        )
        self.assertFalse(result["stage1"]["visibilitySent"])
        self.assertTrue(result["stage1"]["pollUrlPresent"])
        self.assertTrue(result["stage1"]["trackIdPresent"])
        self.assertEqual(result["playlist"]["observedVisibility"], "private")

    def test_parser_has_no_default_stage1_host(self) -> None:
        parser = poc.build_parser()
        args = parser.parse_args([
            "prepare",
            "--file",
            "owned.mp3",
            "--playlist-kind",
            "1055",
        ])
        self.assertIsNone(args.stage1_base_url)


if __name__ == "__main__":
    unittest.main()
