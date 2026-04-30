"""Tests for provider registry, capabilities and storage metadata."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from musicark.providers import (
    LocalLibraryProviderStub,
    ProviderRegistry,
    ProviderRegistryError,
    TrackSource,
    YandexMusicProviderStub,
)
from musicark.storage.database import initialize_database
from musicark.storage.provider_storage import ProviderStorageRepository


class ProviderRegistryTests(unittest.TestCase):
    def test_registry_register_and_get_provider(self) -> None:
        registry = ProviderRegistry()
        provider = YandexMusicProviderStub()
        registry.register(provider)

        actual = registry.get("yandex_music")
        self.assertEqual(actual.provider_id, "yandex_music")
        self.assertIn("yandex_music", registry.list_ids())

    def test_registry_rejects_duplicate_provider_ids(self) -> None:
        registry = ProviderRegistry()
        registry.register(YandexMusicProviderStub())

        with self.assertRaises(ProviderRegistryError):
            registry.register(YandexMusicProviderStub())

    def test_stub_capabilities_are_provider_agnostic(self) -> None:
        yandex = YandexMusicProviderStub()
        local = LocalLibraryProviderStub()

        self.assertTrue(yandex.capabilities.can_authenticate)
        self.assertFalse(yandex.capabilities.can_download_tracks)
        self.assertTrue(local.capabilities.supports_user_uploads)
        self.assertFalse(local.capabilities.can_scan_library)


class ProviderStorageTests(unittest.TestCase):
    def test_provider_and_track_source_metadata_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            repository = ProviderStorageRepository(db_path)

            repository.upsert_provider(
                YandexMusicProviderStub(),
                metadata={"environment": "test", "note": "stub"},
            )
            repository.upsert_track_source(
                TrackSource(
                    track_id="track-1",
                    source_type="yandex_music",
                    provider_id="yandex_music",
                    external_id="12345",
                    availability="available",
                    raw_data={"provider_status": "ok"},
                )
            )

            with closing(sqlite3.connect(db_path)) as conn:
                provider_row = conn.execute(
                    "SELECT provider_id, metadata_json FROM providers WHERE provider_id=?",
                    ("yandex_music",),
                ).fetchone()
                source_row = conn.execute(
                    "SELECT provider_id, external_id, raw_data_json FROM track_sources WHERE provider_id=?",
                    ("yandex_music",),
                ).fetchone()

            self.assertIsNotNone(provider_row)
            self.assertEqual(provider_row[0], "yandex_music")
            self.assertEqual(json.loads(provider_row[1])["environment"], "test")

            self.assertIsNotNone(source_row)
            self.assertEqual(source_row[1], "12345")
            self.assertEqual(json.loads(source_row[2])["provider_status"], "ok")


if __name__ == "__main__":
    unittest.main()
