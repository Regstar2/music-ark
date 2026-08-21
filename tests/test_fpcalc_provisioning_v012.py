from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from musicark.external_metadata.fingerprint import FpcalcProvisioner, FingerprintService
from musicark.storage.database import initialize_database
from musicark.storage.external_metadata_migration import migrate_external_metadata_v012


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.url = FpcalcProvisioner.WINDOWS_X64_URL
        self.headers = {"Content-Length": str(len(payload))}
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self._payload


class FpcalcProvisioningV012Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "musicark.db"
        initialize_database(self.db)
        with sqlite3.connect(self.db) as conn:
            with conn:
                migrate_external_metadata_v012(conn)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_provisioner_extracts_verified_official_archive_to_musicark_tools(self) -> None:
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("chromaprint-fpcalc-test/fpcalc.exe", b"fake-fpcalc")
        payload = archive_bytes.getvalue()

        def runner(args, **kwargs):
            del kwargs
            self.assertEqual(args[-1], "-version")
            return subprocess.CompletedProcess(args, 0, "fpcalc version test", "")

        provisioner = FpcalcProvisioner(
            self.db,
            runner=runner,
            http_get=lambda *args, **kwargs: _FakeResponse(payload),
        )
        with (
            patch.object(FpcalcProvisioner, "_is_windows_x64", return_value=True),
            patch.object(FpcalcProvisioner, "WINDOWS_X64_SHA256", hashlib.sha256(payload).hexdigest()),
        ):
            resolved = Path(provisioner.install())

        self.assertEqual(resolved, self.db.parent / "tools" / "chromaprint" / FpcalcProvisioner.VERSION / "fpcalc.exe")
        self.assertEqual(resolved.read_bytes(), b"fake-fpcalc")

    def test_fingerprint_service_uses_managed_provisioner_without_path_setup(self) -> None:
        audio = self.root / "track.mp3"
        audio.write_bytes(b"audio")
        provision_calls = 0

        def provision() -> str:
            nonlocal provision_calls
            provision_calls += 1
            return "managed-fpcalc.exe"

        def runner(args, **kwargs):
            del kwargs
            self.assertEqual(args[0], "managed-fpcalc.exe")
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps({"fingerprint": "managed-fingerprint", "duration": 12}),
                "",
            )

        service = FingerprintService(self.db, runner=runner, provisioner=provision)
        result = service.fingerprint(123, audio)
        self.assertEqual(result.fingerprint, "managed-fingerprint")
        self.assertEqual(provision_calls, 1)


if __name__ == "__main__":
    unittest.main()
