"""Tests for v0.3 Yandex Library orchestration and playlist cache semantics."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.providers.yandex_music_provider import YandexMusicError
from musicark.storage.liked_cache import LikedCacheRepository
from musicark.storage.playlist_cache import PlaylistCacheRepository
from musicark.yandex_library import YandexLibraryService


class FakeCredentialStore:
    def __init__(self, token: str | None = None) -> None:
        self.token = token
    def get_token(self) -> str | None:
        return self.token
    def set_token(self, token: str) -> None:
        self.token = token
    def delete_token(self) -> None:
        self.token = None


def track(external_id: str, title: str) -> ProviderTrack:
    return ProviderTrack(provider_id="yandex_music", external_id=external_id, title=title, artists=("Artist",), album_title="Album", duration_seconds=180, availability="available")


def playlist(external_id: str, title: str, count: int) -> ProviderPlaylist:
    return ProviderPlaylist(provider_id="yandex_music", external_id=external_id, title=title, track_external_ids=(), owner_name="Tester", visibility="private", raw_data={"track_count": count})


class FakeProvider:
    def __init__(self) -> None:
        self.liked = [track("l1", "Liked One")]
        self.playlist_index = [playlist("10", "Rock", 2), playlist("20", "Workout", 1)]
        self.playlist_tracks = {"10": [track("1", "One"), track("2", "Two")], "20": [track("3", "Three")]}
        self.offline = False
        self.content_calls = 0
    def _check(self) -> None:
        if self.offline:
            raise YandexMusicError("offline")
    def auth_check(self) -> dict:
        self._check(); return {"provider": "yandex_music", "providerUserId": "u-1", "displayName": "Tester"}
    def list_tracks(self) -> list[ProviderTrack]:
        self._check(); return list(self.liked)
    def list_playlist_metadata(self) -> list[ProviderPlaylist]:
        self._check(); return list(self.playlist_index)
    def get_playlist(self, external_id: str) -> tuple[ProviderPlaylist, list[ProviderTrack]]:
        self._check(); self.content_calls += 1
        metadata = next(item for item in self.playlist_index if item.external_id == external_id)
        return metadata, list(self.playlist_tracks.get(external_id, []))


class YandexLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_dir = Path(self.tmp.name)
        self.database = self.base_dir / ".musicark" / "musicark.db"
        self.credentials = FakeCredentialStore()
        self.provider = FakeProvider()
        self.liked_cache = LikedCacheRepository(self.database)
        self.playlist_cache = PlaylistCacheRepository(self.database)
        self.service = YandexLibraryService(base_dir=self.base_dir, credential_store=self.credentials, liked_cache=self.liked_cache, playlist_cache=self.playlist_cache, provider_factory=lambda token: self.provider)  # type: ignore[arg-type]
    def tearDown(self) -> None:
        self.tmp.cleanup()
    def test_login_caches_playlist_metadata_without_fetching_contents(self) -> None:
        result = self.service.login("secret")
        self.assertEqual(result["playlists"]["source"], "network")
        self.assertEqual([p["externalId"] for p in result["playlists"]["items"]], ["10", "20"])
        self.assertEqual(result["playlists"]["items"][0]["trackCount"], 2)
        self.assertEqual(self.provider.content_calls, 0)
        cached = self.service.bootstrap()
        self.assertEqual(cached["playlists"]["source"], "cache")
        self.assertEqual(cached["playlists"]["count"], 2)
    def test_playlist_snapshot_preserves_order_and_reorder(self) -> None:
        self.service.login("secret")
        first = self.service.playlist_refresh("10")
        self.assertEqual([t["external_id"] for t in first["collection"]["tracks"]], ["1", "2"])
        self.provider.playlist_tracks["10"] = [track("2", "Two"), track("1", "One")]
        second = self.service.playlist_refresh("10")
        self.assertEqual(second["collection"]["diff"], {"added": 0, "removed": 0, "unchanged": 2})
        self.assertEqual([t["external_id"] for t in second["collection"]["tracks"]], ["2", "1"])
    def test_playlist_membership_added_removed_and_duplicate_track_ids(self) -> None:
        self.service.login("secret"); self.service.playlist_refresh("10")
        self.provider.playlist_tracks["10"] = [track("2", "Two"), track("2", "Two duplicate occurrence"), track("4", "Four")]
        result = self.service.playlist_refresh("10")
        self.assertEqual(result["collection"]["diff"], {"added": 2, "removed": 1, "unchanged": 1})
        self.assertEqual([t["external_id"] for t in result["collection"]["tracks"]], ["2", "2", "4"])
    def test_library_refresh_removes_deleted_playlist_and_deduplicates_index(self) -> None:
        self.service.login("secret"); self.service.playlist_refresh("10")
        self.provider.playlist_index = [playlist("20", "Workout", 1), playlist("20", "Duplicate should be ignored", 999)]
        result = self.service.library_refresh()
        self.assertEqual(result["playlists"]["diff"]["removed"], 1)
        self.assertEqual([p["externalId"] for p in result["playlists"]["items"]], ["20"])
        self.assertEqual(self.service.playlist("10")["collection"]["tracks"], [])
    def test_empty_playlist_and_offline_cache_behavior(self) -> None:
        self.provider.playlist_index = [playlist("30", "Empty", 0)]; self.provider.playlist_tracks["30"] = []
        self.service.login("secret")
        self.assertEqual(self.service.playlist_refresh("30")["collection"]["count"], 0)
        self.provider.playlist_index = [playlist("10", "Rock", 2)]; self.provider.playlist_tracks["10"] = [track("1", "One"), track("2", "Two")]
        self.service.library_refresh(); self.service.playlist_refresh("10"); self.provider.offline = True
        with self.assertRaises(YandexMusicError):
            self.service.playlist_refresh("10")
        cached = self.service.playlist("10")
        self.assertEqual(cached["collection"]["source"], "cache")
        self.assertEqual([t["external_id"] for t in cached["collection"]["tracks"]], ["1", "2"])
    def test_library_refresh_is_lazy_for_playlist_contents(self) -> None:
        self.service.login("secret"); self.provider.content_calls = 0; self.service.library_refresh()
        self.assertEqual(self.provider.content_calls, 0)
    def test_logout_clears_session_liked_and_playlist_cache(self) -> None:
        self.service.login("secret"); self.service.playlist_refresh("10")
        result = self.service.logout()
        self.assertFalse(result["session"]["hasStoredToken"]); self.assertIsNone(self.credentials.token)
        self.assertEqual(self.liked_cache.load().count, 0); self.assertEqual(self.playlist_cache.list_metadata(), [])


if __name__ == "__main__":
    unittest.main()
