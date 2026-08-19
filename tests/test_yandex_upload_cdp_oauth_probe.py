"""Offline tests for the Chromium/Electron OAuth stage-one diagnostic probe."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_cdp_oauth_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_cdp_oauth_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = probe
_SPEC.loader.exec_module(probe)


class _FakeCdpClient:
    runtime_value: dict = {}
    last_expression: str = ""

    def __init__(self, url: str) -> None:
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def call(self, method: str, params=None, *, timeout: float = 5.0):  # noqa: ANN001
        if method == "Runtime.enable":
            return {}
        if method == "Runtime.evaluate":
            type(self).last_expression = str((params or {}).get("expression") or "")
            return {"result": {"type": "object", "value": dict(type(self).runtime_value)}}
        raise AssertionError(f"Unexpected CDP method: {method}")


class YandexUploadCdpOauthProbeTests(unittest.TestCase):
    def _args(self, file_path: Path, *, base_dir: Path | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            base_dir=str(base_dir) if base_dir is not None else None,
            file=str(file_path),
            playlist_kind="1055",
            stage1_base_url="https://api.music.yandex.net",
            playlist_id_source="uuid",
            path_mode="full",
            confirm_owned_file=True,
            confirm_prepare=True,
            port=9222,
            target_contains="Yandex",
            launch_exe=None,
            launch_wait=0.0,
            timeout=10.0,
        )

    def _context(self, file_path: Path) -> probe._CachedStage1Context:  # noqa: SLF001
        return probe._CachedStage1Context(  # noqa: SLF001
            file_path=file_path,
            uid="uid-secret",
            playlist_id="playlist-uuid-secret",
            playlist_id_source="uuid-cache",
            playlist_id_fallback=False,
            observed_visibility=None,
        )

    def _patch_common(self, file_path: Path):
        return (
            patch.object(probe.live, "_require_research_opt_in"),
            patch.object(probe, "_cached_stage1_context", return_value=self._context(file_path)),
            patch.object(
                probe.live,
                "_prepare_context",
                side_effect=AssertionError("Chromium isolation probe must not initialize the Python Yandex client."),
            ),
            patch.object(probe.live, "_saved_token", return_value="oauth-secret"),
            patch.object(probe.groundtruth, "_launch_desktop"),
            patch.object(
                probe.groundtruth,
                "_discover_target",
                return_value={
                    "type": "page",
                    "title": "Yandex Music",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
                },
            ),
            patch.object(probe.cdp, "CdpClient", _FakeCdpClient),
        )

    def _run_with_common_patches(self, file_path: Path):
        patches = self._patch_common(file_path)
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return probe.run(self._args(file_path))

    def _write_cache(self, root: Path, *, include_uuid: bool) -> Path:
        config_dir = root / ".musicark"
        config_dir.mkdir(parents=True, exist_ok=True)
        database_path = config_dir / "musicark.db"
        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "database_path": ".musicark/musicark.db",
                    "experimental_yandex_upload": True,
                }
            ),
            encoding="utf-8",
        )
        with closing(sqlite3.connect(database_path)) as conn:
            conn.execute(
                """
                CREATE TABLE provider_collection_snapshots(
                    provider_id TEXT,
                    collection_id TEXT,
                    account_json TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE provider_playlists(
                    provider_id TEXT,
                    external_id TEXT,
                    payload_json TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO provider_collection_snapshots VALUES (?, 'liked', ?, '{}')",
                ("yandex_music", json.dumps({"providerUserId": "uid-secret"})),
            )
            conn.execute(
                "INSERT INTO provider_collection_snapshots VALUES (?, ?, '{}', ?)",
                (
                    "yandex_music",
                    "playlist:1055",
                    json.dumps({"externalId": "1055", "visibility": "private"}),
                ),
            )
            if include_uuid:
                conn.execute(
                    "INSERT INTO provider_playlists VALUES (?, ?, ?, datetime('now'))",
                    (
                        "yandex_music",
                        "1055",
                        json.dumps(
                            {
                                "visibility": "private",
                                "raw_data": {"playlist_uuid": "playlist-uuid-secret"},
                            }
                        ),
                    ),
                )
            conn.commit()
        return database_path

    def test_success_proves_chromium_path_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": True,
                "httpStatus": 200,
                "responseShape": {
                    "type": "object",
                    "keys": {
                        "post-target": {"type": "string"},
                        "poll-result": {"type": "string"},
                        "ugc-track-id": {"type": "string"},
                    },
                },
                "postTargetPresent": True,
                "pollResultPresent": True,
                "ugcTrackIdPresent": True,
            }
            payload, code = self._run_with_common_patches(file_path)

            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "upload_url_obtained")
            self.assertEqual(payload["diagnosis"], "python-transport-mismatch-confirmed")
            self.assertTrue(payload["stage1"]["uploadUrlPresent"])
            self.assertFalse(payload["network"]["stage2Sent"])
            self.assertEqual(payload["network"]["browserCredentialsMode"], "omit")
            self.assertFalse(payload["stage1"]["pythonYandexClientInitialized"])
            self.assertEqual(payload["playlist"]["contextSource"], "musicark-local-cache")
            self.assertTrue(payload["safety"]["audio_bytes_sent"] is False)

            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("oauth-secret", serialized)
            self.assertNotIn("uid-secret", serialized)
            self.assertNotIn("playlist-uuid-secret", serialized)
            self.assertIn("credentials: 'omit'", _FakeCdpClient.last_expression)
            self.assertIn("oauth-secret", _FakeCdpClient.last_expression)

    def test_http_403_distinguishes_network_from_credential_or_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": True,
                "httpStatus": 403,
                "responseShape": {"type": "unavailable"},
                "postTargetPresent": False,
                "pollResultPresent": False,
                "ugcTrackIdPresent": False,
            }
            payload, code = self._run_with_common_patches(file_path)

            self.assertEqual(code, 3)
            self.assertTrue(payload["stage1"]["httpResponseReceived"])
            self.assertEqual(payload["stage1"]["httpStatus"], 403)
            self.assertEqual(payload["diagnosis"], "credential-or-required-request-profile-rejected")
            self.assertFalse(payload["stage1"]["desktopSessionCredentialsAttached"])

    def test_browser_network_error_reports_class_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            _FakeCdpClient.runtime_value = {
                "networkCompleted": False,
                "errorName": "TypeError",
            }
            payload, code = self._run_with_common_patches(file_path)

            self.assertEqual(code, 3)
            self.assertEqual(payload["diagnosis"], "chromium-network-path-failed")
            self.assertEqual(payload["stage1"]["networkErrorClass"], "TypeError")
            self.assertIsNone(payload["stage1"]["httpStatus"])

    def test_cached_context_uses_account_and_playlist_uuid_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cache(root, include_uuid=True)
            file_path = root / "owned.mp3"
            file_path.write_bytes(b"audio")
            context = probe._cached_stage1_context(self._args(file_path, base_dir=root), root)  # noqa: SLF001

            self.assertEqual(context.uid, "uid-secret")
            self.assertEqual(context.playlist_id, "playlist-uuid-secret")
            self.assertEqual(context.playlist_id_source, "uuid-cache")
            self.assertFalse(context.playlist_id_fallback)
            self.assertEqual(context.observed_visibility, "private")

    def test_cached_context_falls_back_to_kind_for_network_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cache(root, include_uuid=False)
            file_path = root / "owned.mp3"
            file_path.write_bytes(b"audio")
            context = probe._cached_stage1_context(self._args(file_path, base_dir=root), root)  # noqa: SLF001

            self.assertEqual(context.uid, "uid-secret")
            self.assertEqual(context.playlist_id, "1055")
            self.assertEqual(context.playlist_id_source, "kind-diagnostic-fallback")
            self.assertTrue(context.playlist_id_fallback)

    def test_parser_accepts_no_token_or_cookie_input(self) -> None:
        parser = probe.build_parser()
        options = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        self.assertIn("--stage1-base-url", options)
        self.assertIn("--launch-exe", options)
        self.assertNotIn("--token", options)
        self.assertNotIn("--oauth-token", options)
        self.assertNotIn("--cookie", options)
        self.assertNotIn("--session", options)

    def test_confirm_prepare_is_required_before_cdp_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "owned.mp3"
            file_path.write_bytes(b"audio")
            args = self._args(file_path)
            args.confirm_prepare = False
            with self.assertRaisesRegex(probe.YandexUploadProtocolError, "requires --confirm-prepare"):
                probe.run(args)


if __name__ == "__main__":
    unittest.main()