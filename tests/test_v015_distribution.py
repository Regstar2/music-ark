from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import httpx

from musicark.feedback import feedback_link
from musicark.runtime_cli import _configure_utf8_stdio, _rewrite_packaged_arguments
from musicark.update.models import AppVersion, UpdateError, UpdateErrorCode, UpdateManifest
from musicark.update.service import UpdateService

ROOT = Path(__file__).resolve().parents[1]


class _Transport:
    def __init__(self, responses: dict[str, httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> httpx.Response:
        self.calls.append(url)
        response = self.responses[url]
        if response.request is None:
            response.request = httpx.Request("GET", url)
        return response


def _response(url: str, status: int, *, json_payload=None, content: bytes | None = None, headers=None) -> httpx.Response:
    if json_payload is not None:
        content = json.dumps(json_payload).encode("utf-8")
        headers = {**(headers or {}), "content-type": "application/json"}
    return httpx.Response(status, content=content or b"", headers=headers or {}, request=httpx.Request("GET", url))


class VersionContractTests(unittest.TestCase):
    def test_strict_versions_are_orderable(self) -> None:
        self.assertLess(AppVersion.parse("0.15.0"), AppVersion.parse("1.0.0"))
        with self.assertRaises(ValueError):
            AppVersion.parse("v1.0.0")
        with self.assertRaises(ValueError):
            AppVersion.parse("1.0")

    def test_manifest_requires_hash_size_and_plain_exe_name(self) -> None:
        payload = {
            "schemaVersion": 1,
            "channel": "stable",
            "version": "1.0.0",
            "publishedAt": "2026-08-22T00:00:00Z",
            "installer": {
                "url": "https://github.com/Regstar2/music-ark-releases/releases/download/v1.0.0/MusicArk.exe",
                "sha256": "a" * 64,
                "sizeBytes": 10,
                "fileName": "MusicArk.exe",
            },
        }
        manifest = UpdateManifest.from_dict(payload)
        self.assertEqual(str(manifest.version), "1.0.0")
        payload["installer"]["fileName"] = "../MusicArk.exe"
        with self.assertRaises(ValueError):
            UpdateManifest.from_dict(payload)


class UpdateServiceTests(unittest.TestCase):
    def _fixture(self):
        manifest_url = "https://raw.githubusercontent.com/Regstar2/music-ark-releases/main/stable.json"
        asset_url = "https://github.com/Regstar2/music-ark-releases/releases/download/v0.16.0/MusicArk-Setup-0.16.0-x64.exe"
        payload = b"verified-installer"
        manifest = {
            "schemaVersion": 1,
            "channel": "stable",
            "version": "0.16.0",
            "publishedAt": "2026-08-22T00:00:00Z",
            "installer": {
                "url": asset_url,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "sizeBytes": len(payload),
                "fileName": "MusicArk-Setup-0.16.0-x64.exe",
            },
            "releaseNotesUrl": "https://github.com/Regstar2/music-ark-releases/releases/tag/v0.16.0",
        }
        return manifest_url, asset_url, payload, manifest

    def test_check_is_read_only_and_detects_newer_version(self) -> None:
        manifest_url, _, _, manifest = self._fixture()
        transport = _Transport({manifest_url: _response(manifest_url, 200, json_payload=manifest)})
        with tempfile.TemporaryDirectory() as temp:
            service = UpdateService(Path(temp), current_version="0.15.0", manifest_url=manifest_url, transport=transport)  # type: ignore[arg-type]
            result = service.check()
            self.assertTrue(result["available"])
            self.assertEqual(result["latest"]["version"], "0.16.0")
            self.assertFalse((Path(temp) / ".musicark" / "updates").exists())

    def test_prepare_follows_only_trusted_https_redirect_and_verifies_bytes(self) -> None:
        manifest_url, asset_url, payload, manifest = self._fixture()
        redirected = "https://release-assets.githubusercontent.com/example/MusicArk-Setup-0.16.0-x64.exe?token=x"
        transport = _Transport(
            {
                manifest_url: _response(manifest_url, 200, json_payload=manifest),
                asset_url: _response(asset_url, 302, headers={"location": redirected}),
                redirected: _response(redirected, 200, content=payload),
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            service = UpdateService(Path(temp), current_version="0.15.0", manifest_url=manifest_url, transport=transport)  # type: ignore[arg-type]
            result = service.prepare()
            self.assertTrue(result["available"])
            self.assertFalse(result["cached"])
            target = Path(temp) / ".musicark" / "updates" / manifest["installer"]["fileName"]
            self.assertEqual(target.read_bytes(), payload)
            marker = json.loads((target.parent / "prepared.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["manifest"]["installer"]["sha256"], hashlib.sha256(payload).hexdigest())

    def test_hash_mismatch_never_promotes_part_file(self) -> None:
        manifest_url, asset_url, payload, manifest = self._fixture()
        bad_manifest = json.loads(json.dumps(manifest))
        bad_manifest["installer"]["sha256"] = "f" * 64
        transport = _Transport(
            {
                manifest_url: _response(manifest_url, 200, json_payload=bad_manifest),
                asset_url: _response(asset_url, 200, content=payload),
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            service = UpdateService(Path(temp), current_version="0.15.0", manifest_url=manifest_url, transport=transport)  # type: ignore[arg-type]
            with self.assertRaises(UpdateError) as ctx:
                service.prepare()
            self.assertEqual(ctx.exception.code, UpdateErrorCode.HASH_MISMATCH)
            update_dir = Path(temp) / ".musicark" / "updates"
            self.assertFalse(any(update_dir.glob("*.exe")) if update_dir.exists() else False)

    def test_untrusted_manifest_url_fails_closed_before_network(self) -> None:
        transport = _Transport({})
        with tempfile.TemporaryDirectory() as temp:
            service = UpdateService(Path(temp), current_version="0.15.0", manifest_url="http://example.com/stable.json", transport=transport)  # type: ignore[arg-type]
            with self.assertRaises(UpdateError) as ctx:
                service.check()
            self.assertEqual(ctx.exception.code, UpdateErrorCode.UNTRUSTED_URL)
            self.assertEqual(transport.calls, [])


class FeedbackAndRuntimeTests(unittest.TestCase):
    def test_bug_feedback_uses_issue_form_and_safe_diagnostics_only(self) -> None:
        link = feedback_link("bug")
        self.assertIn("github.com/Regstar2/music-ark/issues/new", link.url)
        self.assertIn("bug_report.yml", link.url)
        self.assertNotIn("YANDEX_MUSIC_TOKEN", link.url)
        self.assertNotIn(str(Path.home()), link.url)

    def test_frozen_runtime_rewrites_legacy_base_dir_to_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(sys, "frozen", True, create=True), mock.patch.dict(
                os.environ,
                {"LOCALAPPDATA": temp},
                clear=False,
            ):
                args = _rewrite_packaged_arguments(["--base-dir", r"C:\Program Files\MusicArk", "bootstrap"])
            expected = str(Path(temp) / "MusicArk")
            self.assertEqual(args[:2], ["--base-dir", expected])
            self.assertTrue(Path(expected).is_dir())

    def test_frozen_runtime_reconfigures_stdio_to_utf8(self) -> None:
        import io

        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="cp1251")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="cp1251")

        _configure_utf8_stdio(stdout=stdout, stderr=stderr)
        print(json.dumps({"message": "кириллица \u04c4"}, ensure_ascii=False), file=stdout)
        stdout.flush()

        self.assertIn("кириллица \u04c4", stdout_bytes.getvalue().decode("utf-8"))


class WindowsPackagingNameTests(unittest.TestCase):
    def test_flutter_runner_name_is_preserved_until_release_staging(self) -> None:
        runner_cmake = (ROOT / "ui/musicark_ui/windows/runner/CMakeLists.txt").read_text(encoding="utf-8")
        package_script = (ROOT / "tools/package_windows.ps1").read_text(encoding="utf-8")

        self.assertNotIn('OUTPUT_NAME "Music Ark"', runner_cmake)
        self.assertIn('$appExeName = "Music Ark.exe"', package_script)
        self.assertIn('$flutterExeName = "musicark_ui.exe"', package_script)
        self.assertIn('$flutterExe = Join-Path $flutterOutput $flutterExeName', package_script)
        self.assertIn('Move-Item -LiteralPath $stagedFlutterExe -Destination $stagedAppExe -Force', package_script)
        self.assertNotIn('$appExeName = "musicark_ui.exe"', package_script)

    def test_installer_launches_music_ark_exe(self) -> None:
        iss = (ROOT / "packaging/windows/MusicArk.iss").read_text(encoding="utf-8")
        resources = (ROOT / "ui/musicark_ui/windows/runner/Runner.rc").read_text(encoding="utf-8")

        self.assertIn('#define MyAppName "Music Ark"', iss)
        self.assertIn('#define MyAppExeName "Music Ark.exe"', iss)
        self.assertIn('Name: "{autoprograms}\\Music Ark"', iss)
        self.assertIn('VALUE "OriginalFilename", "Music Ark.exe"', resources)
        self.assertIn('VALUE "ProductName", "Music Ark"', resources)


if __name__ == "__main__":
    unittest.main()
