"""Tests for matching-engine and canonical-library links."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.matching.engine import MatchingEngine
from musicark.matching.normalize import normalize_text
from musicark.providers.models import LocalAudioFile, ProviderCapabilities, ProviderTrack, TrackSource
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.storage.provider_storage import ProviderStorageRepository


class DummyProvider:
    provider_id = "yandex_music"
    display_name = "Yandex"
    capabilities = ProviderCapabilities(
        can_authenticate=True,
        can_scan_library=True,
        can_scan_playlists=True,
        can_download_tracks=True,
        can_upload_tracks=False,
        can_create_playlists=False,
        can_edit_playlists=False,
        supports_track_availability=True,
        supports_user_uploads=False,
    )


class MatchingEngineTests(unittest.TestCase):
    def test_normalize_text_sanitizes_case_and_symbols(self) -> None:
        self.assertEqual(normalize_text("  AheGao!!! "), "ahegao")
        self.assertEqual(normalize_text("Thousand Foot Krutch"), "thousand foot krutch")

    def test_exact_id_match_creates_track_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider_storage = ProviderStorageRepository(db_path)
            local_storage = LocalLibraryStorageRepository(db_path)

            provider_storage.upsert_provider(DummyProvider(), metadata={"seed": True})
            provider_storage.upsert_provider_track(
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="69046542",
                    title="Ахегао",
                    artists=("Мэйби Бэйби",),
                    duration_seconds=160,
                )
            )
            provider_storage.upsert_track_source(
                TrackSource(
                    track_id="provider:yandex_music:69046542",
                    source_type="yandex_music",
                    provider_id="yandex_music",
                    external_id="69046542",
                    availability="available",
                )
            )
            local_id = local_storage.upsert_local_audio_file_and_return_id(
                LocalAudioFile(
                    path=str(Path(tmp) / "yandex_69046542.mp3"),
                    sha256="a" * 64,
                    file_size=1000,
                    duration_seconds=160,
                    codec="mp3",
                )
            )
            self.assertGreater(local_id, 0)

            engine = MatchingEngine(db_path)
            result = engine.run()
            self.assertGreaterEqual(result["linked"], 1)

            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "SELECT confidence, match_method FROM track_links WHERE source_external_id='69046542'"
                ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][1], "exact_id")
            self.assertGreaterEqual(rows[0][0], 0.95)

    def test_low_confidence_match_not_linked_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider_storage = ProviderStorageRepository(db_path)
            local_storage = LocalLibraryStorageRepository(db_path)

            provider_storage.upsert_provider(DummyProvider(), metadata={})
            provider_storage.upsert_provider_track(
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="123",
                    title="Completely Different Name",
                    artists=("Unknown Artist",),
                )
            )
            local_storage.upsert_local_audio_file(
                LocalAudioFile(
                    path=str(Path(tmp) / "random_file.wav"),
                    sha256="b" * 64,
                    file_size=500,
                    duration_seconds=42,
                    codec="wav",
                )
            )

            engine = MatchingEngine(db_path)
            result = engine.run()
            self.assertEqual(result["linked"], 0)

            with closing(sqlite3.connect(db_path)) as conn:
                link_count = conn.execute("SELECT COUNT(*) FROM track_links").fetchone()[0]
            self.assertEqual(link_count, 0)


if __name__ == "__main__":
    unittest.main()
