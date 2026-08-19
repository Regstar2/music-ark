"""Offline tests for the recovered uid:playlistKind Stage1 differential."""

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

_TOOL = _TOOLS / "yandex_upload_cdp_composite_playlist_id_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_composite_playlist_id_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadCdpCompositePlaylistIdProbeTests(unittest.TestCase):
    @staticmethod
    def _args() -> argparse.Namespace:
        return argparse.Namespace(
            file="owned.mp3",
            playlist_kind="1055",
            playlist_id_source="uuid",
            path_mode="name",
        )

    def test_composite_context_uses_exact_recovered_formula(self) -> None:
        base = probe.path_probe.uuid_probe.language.noauth.base
        cached = base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="123456",
            playlist_id="ignored-uuid",
            playlist_id_source="uuid-cache-metadata",
            playlist_id_fallback=False,
            observed_visibility="public",
        )
        with mock.patch.object(probe, "_ORIGINAL_CONTEXT", return_value=cached):
            context = probe._composite_context(self._args(), None)  # noqa: SLF001
        self.assertEqual(context.playlist_id, "123456:1055")
        self.assertEqual(context.playlist_id_source, probe._SOURCE)  # noqa: SLF001
        self.assertFalse(context.playlist_id_fallback)

    def test_composite_context_rejects_nonbaseline_source(self) -> None:
        args = self._args()
        args.playlist_id_source = "kind"
        base = probe.path_probe.uuid_probe.language.noauth.base
        cached = base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="123456",
            playlist_id="1055",
            playlist_id_source="kind",
            playlist_id_fallback=False,
            observed_visibility=None,
        )
        with mock.patch.object(probe, "_ORIGINAL_CONTEXT", return_value=cached):
            with self.assertRaises(base.YandexUploadProtocolError):
                probe._composite_context(args, None)  # noqa: SLF001

    def test_run_restores_uuid_hook_and_marks_only_composite_differential(self) -> None:
        original_hook = probe.path_probe.uuid_probe._uuid_context  # noqa: SLF001
        captured: dict[str, object] = {}

        def fake_path_run(args):  # noqa: ANN001, ANN202
            captured["hook"] = probe.path_probe.uuid_probe._uuid_context  # noqa: SLF001
            return (
                {
                    "format": "old",
                    "playlist": {
                        "playlistIdSourceUsed": "uuid-cache-metadata",
                        "playlistIdDiagnosticFallback": False,
                    },
                    "file": {"stage1PathMode": "name"},
                    "stage1": {"authorizationSource": "none"},
                    "probe": {"differentialVariable": "path-full-to-filename"},
                    "safety": {
                        "credential_values_included": False,
                        "query_values_included": False,
                        "authorization_header_sent": False,
                        "audio_bytes_sent": False,
                    },
                },
                3,
            )

        with mock.patch.object(probe.path_probe, "run", side_effect=fake_path_run):
            payload, code = probe.run(self._args())

        self.assertEqual(code, 3)
        self.assertIs(captured["hook"], probe._composite_context)  # noqa: SLF001
        self.assertIs(probe.path_probe.uuid_probe._uuid_context, original_hook)  # noqa: SLF001
        self.assertEqual(payload["playlist"]["playlistIdSourceUsed"], probe._SOURCE)  # noqa: SLF001
        self.assertEqual(payload["playlist"]["playlistIdFormula"], "uid:playlistKind")
        self.assertEqual(
            payload["probe"]["differentialVariable"],
            "playlist-id-cached-uuid-to-uid-colon-kind",
        )
        self.assertFalse(payload["safety"]["playlist_composite_value_included"])
        self.assertFalse(payload["safety"]["authorization_header_sent"])
        self.assertFalse(payload["safety"]["audio_bytes_sent"])

    def test_run_requires_filename_path_baseline(self) -> None:
        args = self._args()
        args.path_mode = "full"
        with self.assertRaises(probe.path_probe.uuid_probe.language.noauth.base.YandexUploadProtocolError):
            probe.run(args)

    def test_parser_has_no_token_cookie_or_composite_value_input(self) -> None:
        parser = probe.path_probe.uuid_probe.language.noauth.base.build_parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        forbidden = {"--token", "--oauth", "--cookie", "--session", "--playlist-id"}
        self.assertTrue(option_strings.isdisjoint(forbidden))


if __name__ == "__main__":
    unittest.main()
