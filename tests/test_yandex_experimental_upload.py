"""Regression tests for the fail-closed v0.10.0 Yandex upload boundary."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.providers.yandex_experimental_upload import (
    client_exposes_upload_api,
    run_experimental_yandex_upload,
)
from musicark.providers.yandex_music_provider import YandexMusicError, YandexMusicProvider
from musicark.storage.database import initialize_database


class YandexUploadFeasibilityTests(unittest.TestCase):
    def test_production_upload_capabilities_remain_disabled(self) -> None:
        capabilities = YandexMusicProvider().capabilities
        self.assertFalse(capabilities.can_upload_tracks)
        self.assertFalse(capabilities.supports_user_uploads)

    def test_compatibility_probe_reports_no_verified_api(self) -> None:
        supported, methods = client_exposes_upload_api()
        self.assertFalse(supported)
        self.assertEqual(methods, [])

    def test_obsolete_experimental_entry_point_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db)

            with self.assertRaisesRegex(YandexMusicError, "BLOCKED"):
                run_experimental_yandex_upload(
                    database_path=db,
                    base_dir=Path(tmp),
                    payload={
                        "confirm": True,
                        "local_file_id": 1,
                        "original_external_id": "12345",
                    },
                )


if __name__ == "__main__":
    unittest.main()
