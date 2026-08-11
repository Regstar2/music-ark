"""Tests for v0.2 persistent session and liked-library cache."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.persistent_library import PersistentLibraryService
from musicark.providers.models import ProviderTrack
from musicark.storage.liked_cache import LikedCacheRepository


class FakeCredentialStore:
    def __init__(self) -> None:
        self.token: str | None = None

    def get_token(self) -> str | None:
        return self.token

    def set_token(self, token: str) -> None:
        self.token = token

    def delete_token(self) -> None:
        self.token = None


class FakeProvider:
    def __init__(self, tracks: list[ProviderTrack]) -> None:
        self.tracks = tracks

    def auth_check(self) -> dict:
        return {
            "provider": "yandex_music",
            "providerUserId": "u-1",
            "displayName": "Tester",
        }

    def list_tracks(self) -> list[ProviderTrack]:
        return list(self.tracks)


def track(external_id: str, title: str) -> ProviderTrack:
    return ProviderTrack(
        provider_id="yandex_music",
        external_id=external_id,
        title=title,
        artists=("Artist",),
        album_title="Album",
    )


class PersistentLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_dir = Path(self.tmp.name)
        self.credentials = FakeCredentialStore()
        self.provider = FakeProvider([track("101", "One"), track("102", "Two")])
        self.cache = LikedCacheRepository(self.base_dir / ".musicark" / "musicark.db")
        self.service = PersistentLibraryService(
            base_dir=self.base_dir,
            credential_store=self.credentials,
            cache=self.cache,
            provider_factory=lambda token: self.provider,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_login_saves_token_and_network_snapshot(self) -> None:
        result = self.service.login("secret-token")
        self.assertEqual(self.credentials.token, "secret-token")
        self.assertEqual(result["library"]["source"], "network")
        self.assertEqual(result["library"]["count"], 2)
        self.assertEqual(result["library"]["diff"]["added"], 2)

        bootstrap = self.service.bootstrap()
        self.assertTrue(bootstrap["session"]["hasStoredToken"])
        self.assertEqual(bootstrap["library"]["source"], "cache")
        self.assertEqual(bootstrap["library"]["count"], 2)

    def test_refresh_replaces_snapshot_and_reports_removed_items(self) -> None:
        self.service.login("secret-token")
        self.provider.tracks = [track("102", "Two"), track("103", "Three")]

        result = self.service.refresh()
        self.assertEqual(result["library"]["diff"], {"added": 1, "removed": 1, "unchanged": 1})
        ids = [item["external_id"] for item in result["library"]["tracks"]]
        self.assertEqual(ids, ["102", "103"])

    def test_logout_clears_credentials_and_cache(self) -> None:
        self.service.login("secret-token")
        result = self.service.logout()
        self.assertFalse(result["session"]["hasStoredToken"])
        self.assertIsNone(self.credentials.token)
        self.assertEqual(self.cache.load().count, 0)


if __name__ == "__main__":
    unittest.main()
