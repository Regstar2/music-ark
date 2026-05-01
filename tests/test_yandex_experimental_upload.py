"""Tests experimental Yandex upload scaffolding (v0.11)."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from musicark.core.config import AppConfig, save_config
from musicark.providers.models import LocalAudioFile
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.providers.yandex_experimental_upload import run_experimental_yandex_upload
from musicark.providers.yandex_upload_mapping import build_upload_replacement_mapping
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


class ExperimentalUploadProbeTests(unittest.TestCase):
    def test_mapping_placeholder(self) -> None:
        payload = build_upload_replacement_mapping(
            original_external_id="9",
            local_file_id=2,
            uploaded_external_id=None,
            upload_status="not_supported",
            detail="test",
        )
        self.assertIn("detail", payload)
        self.assertFalse(payload["replacement_ready"])

    def test_attempt_not_supported_writes_audit_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            db = base_dir / ".musicark" / "musicark.db"
            initialize_database(db)
            save_config(AppConfig(experimental_yandex_upload=True), base_dir)

            fp = base_dir / "sample.mp3"
            fp.write_bytes(b"MZ")
            local_id = LocalLibraryStorageRepository(db).upsert_local_audio_file_and_return_id(
                LocalAudioFile(
                    path=str(fp.resolve()),
                    sha256="f" * 64,
                    file_size=len(b"MZ"),
                    duration_seconds=1.5,
                    codec="mp3",
                )
            )

            with patch(
                "musicark.providers.yandex_experimental_upload.client_exposes_upload_api",
                return_value=(False, []),
            ), patch.object(
                YandexMusicProvider,
                "auth_check",
                return_value={"provider": "yandex_music"},
            ):
                result = run_experimental_yandex_upload(
                    database_path=db,
                    base_dir=base_dir,
                    payload={
                        "confirm": True,
                        "local_file_id": local_id,
                        "original_external_id": "12345",
                    },
                )

            self.assertEqual(result["status"], "not_supported")
            with closing(sqlite3.connect(db)) as conn:
                n = conn.execute(
                    """
                    SELECT COUNT(*) FROM audit_log
                    WHERE event_type='experimental_yandex_upload_attempt'
                    """
                ).fetchone()[0]
            self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
