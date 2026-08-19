"""Offline tests for the filename-only Chromium stage-one differential."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_path_name_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_path_name_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadCdpPathNameProbeTests(unittest.TestCase):
    @staticmethod
    def _args(path_mode: str = "name") -> argparse.Namespace:
        return argparse.Namespace(path_mode=path_mode)

    def test_requires_filename_path_mode_before_underlying_probe(self) -> None:
        with mock.patch.object(probe.uuid_probe, "run") as underlying:
            with self.assertRaisesRegex(Exception, "requires --path-mode name"):
                probe.run(self._args("full"))
        underlying.assert_not_called()

    def test_run_changes_only_path_differential_markers(self) -> None:
        source_payload = {
            "format": "musicark-yandex-upload-cdp-playlist-uuid-differential-v1",
            "playlist": {
                "playlistIdSourceUsed": "uuid-cache-metadata",
                "playlistIdDiagnosticFallback": False,
            },
            "file": {"name": "owned.mp3", "extension": ".mp3", "size": 123},
            "stage1": {"authorizationSource": "none"},
            "probe": {"mutation": "stage1-upload-slot-only"},
            "safety": {
                "audio_bytes_sent": False,
                "authorization_header_sent": False,
                "playlist_uuid_value_included": False,
                "playlist_kind_fallback_allowed": False,
            },
        }
        with mock.patch.object(probe.uuid_probe, "run", return_value=(source_payload, 3)) as underlying:
            payload, code = probe.run(self._args())

        underlying.assert_called_once()
        self.assertEqual(code, 3)
        self.assertEqual(payload["format"], "musicark-yandex-upload-cdp-path-name-differential-v1")
        self.assertEqual(payload["playlist"]["playlistIdSourceUsed"], "uuid-cache-metadata")
        self.assertFalse(payload["playlist"]["playlistIdDiagnosticFallback"])
        self.assertEqual(payload["file"]["stage1PathMode"], "name")
        self.assertEqual(payload["probe"]["differentialVariable"], "path-full-to-filename")
        self.assertFalse(payload["safety"]["path_value_included"])
        self.assertFalse(payload["safety"]["absolute_path_query_sent"])
        self.assertTrue(payload["safety"]["filename_only_path_query_sent"])
        self.assertFalse(payload["safety"]["audio_bytes_sent"])
        self.assertFalse(payload["safety"]["authorization_header_sent"])
        self.assertFalse(payload["safety"]["playlist_kind_fallback_allowed"])

    def test_parser_exposes_no_secret_inputs(self) -> None:
        parser = probe.uuid_probe.language.noauth.base.build_parser()
        destinations = {action.dest for action in parser._actions}  # noqa: SLF001
        self.assertNotIn("token", destinations)
        self.assertNotIn("cookie", destinations)
        self.assertNotIn("authorization", destinations)


if __name__ == "__main__":
    unittest.main()
