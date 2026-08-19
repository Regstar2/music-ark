"""Offline tests for the cached playlist UUID Chromium differential probe."""

from __future__ import annotations

import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_playlist_uuid_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_playlist_uuid_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class YandexUploadCdpPlaylistUuidProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database = Path(self.tmp.name) / "musicark.db"
        with closing(sqlite3.connect(self.database)) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE provider_collection_snapshots (
                        provider_id TEXT NOT NULL,
                        collection_id TEXT NOT NULL,
                        metadata_json TEXT,
                        collection_type TEXT NOT NULL,
                        active INTEGER NOT NULL
                    )
                    """
                )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _args() -> argparse.Namespace:
        return argparse.Namespace(playlist_kind="1055", playlist_id_source="uuid")

    def _insert_metadata(self, metadata: dict) -> None:
        with closing(sqlite3.connect(self.database)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO provider_collection_snapshots(
                        provider_id, collection_id, metadata_json, collection_type, active
                    ) VALUES ('yandex_music', 'playlist:1055', ?, 'playlist', 1)
                    """,
                    (json.dumps(metadata),),
                )

    def test_cached_playlist_uuid_reads_metadata_without_returning_unrelated_fields(self) -> None:
        self._insert_metadata(
            {"playlistUuid": "playlist-uuid-1055", "title": "not-relevant"}
        )

        with mock.patch.object(
            probe.language.noauth.base,
            "_resolve_database_path",
            return_value=self.database,
        ):
            value = probe._cached_playlist_uuid(self._args(), None)  # noqa: SLF001

        self.assertEqual(value, "playlist-uuid-1055")

    def test_uuid_context_replaces_kind_fallback_and_disables_fallback(self) -> None:
        self._insert_metadata({"playlistUuid": "playlist-uuid-1055"})
        original = probe.language.noauth.base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="user-id",
            playlist_id="1055",
            playlist_id_source="kind-diagnostic-fallback",
            playlist_id_fallback=True,
            observed_visibility="public",
        )

        with (
            mock.patch.object(probe, "_ORIGINAL_CONTEXT", return_value=original),
            mock.patch.object(
                probe.language.noauth.base,
                "_resolve_database_path",
                return_value=self.database,
            ),
        ):
            context = probe._uuid_context(self._args(), None)  # noqa: SLF001

        self.assertEqual(context.playlist_id, "playlist-uuid-1055")
        self.assertEqual(context.playlist_id_source, "uuid-cache-metadata")
        self.assertFalse(context.playlist_id_fallback)

    def test_uuid_context_fails_closed_when_cache_has_no_uuid(self) -> None:
        self._insert_metadata({"externalId": "1055"})
        original = probe.language.noauth.base._CachedStage1Context(  # noqa: SLF001
            file_path=Path("owned.mp3"),
            uid="user-id",
            playlist_id="1055",
            playlist_id_source="kind-diagnostic-fallback",
            playlist_id_fallback=True,
            observed_visibility="public",
        )

        with (
            mock.patch.object(probe, "_ORIGINAL_CONTEXT", return_value=original),
            mock.patch.object(
                probe.language.noauth.base,
                "_resolve_database_path",
                return_value=self.database,
            ),
        ):
            with self.assertRaisesRegex(Exception, "playlist UUID is unavailable"):
                probe._uuid_context(self._args(), None)  # noqa: SLF001

    def test_run_restores_context_hook_and_marks_uuid_value_sanitized(self) -> None:
        base = probe.language.noauth.base
        original_context = base._cached_stage1_context  # noqa: SLF001

        def fake_language_run(_args):
            self.assertIs(base._cached_stage1_context, probe._uuid_context)  # noqa: SLF001
            return (
                {
                    "format": "old",
                    "playlist": {
                        "playlistIdSourceUsed": "kind-diagnostic-fallback",
                        "playlistIdDiagnosticFallback": True,
                    },
                    "probe": {},
                    "safety": {},
                },
                3,
            )

        with mock.patch.object(probe.language, "run", side_effect=fake_language_run):
            payload, code = probe.run(self._args())

        self.assertEqual(code, 3)
        self.assertEqual(
            payload["format"],
            "musicark-yandex-upload-cdp-playlist-uuid-differential-v1",
        )
        self.assertEqual(payload["playlist"]["playlistIdSourceUsed"], "uuid-cache-metadata")
        self.assertFalse(payload["playlist"]["playlistIdDiagnosticFallback"])
        self.assertEqual(payload["probe"]["differentialVariable"], "playlist-id-kind-to-cached-uuid")
        self.assertFalse(payload["safety"]["playlist_uuid_value_included"])
        self.assertFalse(payload["safety"]["playlist_kind_fallback_allowed"])
        self.assertIs(base._cached_stage1_context, original_context)  # noqa: SLF001

    def test_parser_exposes_no_secret_inputs(self) -> None:
        parser = probe.language.noauth.base.build_parser()
        destinations = {action.dest for action in parser._actions}  # noqa: SLF001
        self.assertNotIn("token", destinations)
        self.assertNotIn("cookie", destinations)
        self.assertNotIn("authorization", destinations)


if __name__ == "__main__":
    unittest.main()
