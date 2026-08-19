"""Regression tests for provider-specific Yandex playlist UUID persistence."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.providers.models import ProviderPlaylist
from musicark.storage.playlist_cache import PlaylistCacheRepository


class PlaylistCacheUuidTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database = Path(self.tmp.name) / ".musicark" / "musicark.db"
        self.cache = PlaylistCacheRepository(self.database)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _playlist(raw_data: dict) -> ProviderPlaylist:
        return ProviderPlaylist(
            provider_id="yandex_music",
            external_id="1055",
            title="Upload target",
            track_external_ids=(),
            owner_name="Tester",
            visibility="public",
            raw_data=raw_data,
        )

    def test_replace_index_preserves_playlist_uuid_without_full_raw_payload(self) -> None:
        playlist = self._playlist(
            {
                "playlist_uuid": "playlist-uuid-1055",
                "track_count": 12,
                "unrelated": "must-not-be-copied",
            }
        )

        self.cache.replace_index([playlist])
        metadata = self.cache.list_metadata()[0]

        self.assertEqual(metadata["externalId"], "1055")
        self.assertEqual(metadata["playlistUuid"], "playlist-uuid-1055")
        self.assertEqual(metadata["trackCount"], 12)
        self.assertNotIn("unrelated", metadata)

    def test_replace_playlist_keeps_uuid_in_loaded_snapshot(self) -> None:
        playlist = self._playlist({"playlistUuid": "playlist-uuid-camel"})

        self.cache.replace_playlist(playlist, [])
        snapshot = self.cache.load("1055")

        self.assertEqual(snapshot.metadata["playlistUuid"], "playlist-uuid-camel")

    def test_missing_uuid_does_not_invent_one(self) -> None:
        self.cache.replace_index([self._playlist({"track_count": 0})])

        metadata = self.cache.list_metadata()[0]

        self.assertNotIn("playlistUuid", metadata)


if __name__ == "__main__":
    unittest.main()
