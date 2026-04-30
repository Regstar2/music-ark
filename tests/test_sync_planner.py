"""Tests for sync planner dry-run plan creation and persistence."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.providers.models import LocalAudioFile, ProviderCapabilities, ProviderTrack, TrackSource
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.storage.provider_storage import ProviderStorageRepository
from musicark.sync.planner import SyncPlanner


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


class SyncPlannerTests(unittest.TestCase):
    def test_build_plan_creates_download_and_link_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            provider_storage = ProviderStorageRepository(db)
            local_storage = LocalLibraryStorageRepository(db)
            provider_storage.upsert_provider(DummyProvider(), metadata={})

            provider_storage.upsert_provider_track(
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="111",
                    title="One",
                    artists=("A",),
                    source_type="yandex_music",
                )
            )
            provider_storage.upsert_provider_track(
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="222",
                    title="Two",
                    artists=("B",),
                    source_type="yandex_music",
                )
            )
            local_storage.upsert_local_audio_file(
                LocalAudioFile(
                    path=str(Path(tmp) / "yandex_111.mp3"),
                    sha256="a" * 64,
                    file_size=10,
                    duration_seconds=10,
                    codec="mp3",
                )
            )
            local_storage.upsert_local_audio_file(
                LocalAudioFile(
                    path=str(Path(tmp) / "other_file.mp3"),
                    sha256="b" * 64,
                    file_size=20,
                    duration_seconds=20,
                    codec="mp3",
                )
            )

            planner = SyncPlanner(db)
            plan = planner.build_plan(dry_run=True)

            types = [op.operation_type.value for op in plan.operations]
            self.assertIn("link_local", types)
            self.assertIn("download_track", types)
            self.assertIn("create_download_task", types)
            self.assertIn("needs_review", types)
            self.assertGreater(plan.summary["total"], 0)

    def test_save_show_cancel_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            planner = SyncPlanner(db)
            plan = planner.build_plan()
            loaded = planner.show_plan(plan.id)
            self.assertEqual(loaded.id, plan.id)
            planner.cancel_plan(plan.id)
            # no exception means cancel persisted


if __name__ == "__main__":
    unittest.main()
