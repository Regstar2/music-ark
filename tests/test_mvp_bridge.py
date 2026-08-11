"""Tests for the minimal Yandex likes MVP bridge."""

from __future__ import annotations

from dataclasses import dataclass
import unittest

from musicark.mvp_bridge import liked_tracks, login
from musicark.providers.models import ProviderTrack


@dataclass
class FakeYandexProvider:
    account: dict
    tracks: list[ProviderTrack]

    def auth_check(self) -> dict:
        return self.account

    def list_tracks(self) -> list[ProviderTrack]:
        return self.tracks


class MvpBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeYandexProvider(
            account={
                "provider": "yandex_music",
                "providerUserId": "u-1",
                "displayName": "Tester",
            },
            tracks=[
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="101",
                    title="Courtesy Call",
                    artists=("Thousand Foot Krutch",),
                    album_title="The End Is Where We Begin",
                    duration_seconds=238,
                )
            ],
        )

    def test_login_returns_account_identity(self) -> None:
        result = login(provider=self.provider)
        self.assertEqual(result["providerUserId"], "u-1")
        self.assertEqual(result["displayName"], "Tester")

    def test_liked_tracks_returns_track_payload(self) -> None:
        result = liked_tracks(provider=self.provider)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tracks"][0]["external_id"], "101")
        self.assertEqual(
            result["tracks"][0]["artists"],
            ("Thousand Foot Krutch",),
        )


if __name__ == "__main__":
    unittest.main()
