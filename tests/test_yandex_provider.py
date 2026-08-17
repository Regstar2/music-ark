"""Unit tests for yandex provider mapping and scan persistence."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from musicark.providers.yandex_mapper import (
    map_track_source,
    map_yandex_album,
    map_yandex_playlist,
    map_yandex_track,
)
from musicark.providers.yandex_music_provider import YandexMusicProvider, YandexTokenMissingError
from musicark.storage.database import initialize_database


class FakeYandexProvider(YandexMusicProvider):
    """Yandex provider test double without real network calls."""

    def _build_client(self):  # type: ignore[no-untyped-def]
        return object()

    def auth_check(self) -> dict:
        return {
            "provider": "yandex_music",
            "providerUserId": "u-1",
            "displayName": "Tester",
        }

    def _fetch_liked_tracks_payload(self) -> list[dict]:
        return [
            {
                "id": "101",
                "title": "Courtesy Call",
                "duration_ms": 238000,
                "artists": [{"name": "Thousand Foot Krutch"}],
                "albums": [
                    {
                        "id": "a-1",
                        "title": "The End Is Where We Begin",
                        "cover_uri": "avatars.yandex.net/get-music-content/123/%%",
                    }
                ],
                "available": True,
                "content_warning": False,
            }
        ]

    def _fetch_playlists_payload(self) -> list[dict]:
        return [
            {
                "kind": "501",
                "title": "Favorites",
                "owner": {"name": "Tester"},
                "visibility": "public",
                "track_refs": ["101"],
            }
        ]


class YandexMapperTests(unittest.TestCase):
    def test_map_track_creates_universal_provider_track(self) -> None:
        mapped = map_yandex_track(
            {
                "id": "11",
                "title": "Song",
                "duration_ms": 180000,
                "artists": [{"name": "Artist"}],
                "albums": [
                    {
                        "id": "1",
                        "title": "Album",
                        "cover_uri": "//avatars.yandex.net/get-music-content/42/%%",
                    }
                ],
                "available": True,
            }
        )
        self.assertEqual(mapped.provider_id, "yandex_music")
        self.assertEqual(mapped.external_id, "11")
        self.assertEqual(mapped.duration_seconds, 180)
        self.assertEqual(
            mapped.artwork_url,
            "https://avatars.yandex.net/get-music-content/42/200x200",
        )

    def test_map_album_creates_liked_album_summary(self) -> None:
        mapped = map_yandex_album(
            {
                "id": 77,
                "title": "Favorite Album",
                "artists": [{"name": "Favorite Artist"}],
                "track_count": 12,
                "cover_uri": "//avatars.yandex.net/get-music-content/77/%%",
                "available": True,
                "year": 2026,
            },
            liked_at="2026-08-17T12:00:00+00:00",
        )
        self.assertEqual(mapped["externalId"], "77")
        self.assertEqual(mapped["title"], "Favorite Album")
        self.assertEqual(mapped["artists"], ["Favorite Artist"])
        self.assertEqual(mapped["trackCount"], 12)
        self.assertEqual(mapped["availability"], "available")
        self.assertEqual(
            mapped["artworkUrl"],
            "https://avatars.yandex.net/get-music-content/77/400x400",
        )

    def test_map_playlist_creates_universal_provider_playlist(self) -> None:
        mapped = map_yandex_playlist(
            {
                "kind": "700",
                "title": "Mix",
                "owner": {"name": "Owner"},
                "visibility": "private",
                "track_refs": ["11", "22"],
            }
        )
        self.assertEqual(mapped.provider_id, "yandex_music")
        self.assertEqual(mapped.external_id, "700")
        self.assertEqual(mapped.track_external_ids, ("11", "22"))

    def test_track_source_uses_provider_specific_not_global_id(self) -> None:
        track = map_yandex_track({"id": "55", "title": "T", "artists": []})
        source = map_track_source(track)
        self.assertEqual(source.source_type, "yandex_music")
        self.assertEqual(source.external_id, "55")
        self.assertNotEqual(source.track_id, "55")


class YandexProviderTests(unittest.TestCase):
    def test_missing_token_is_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = YandexMusicProvider(base_dir=Path(tmp))
            with self.assertRaises(YandexTokenMissingError):
                provider._resolve_token()

    def test_repeat_scan_updates_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider = FakeYandexProvider(base_dir=Path(tmp))

            provider.scan_all(db_path)
            provider.scan_all(db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                track_count = conn.execute("SELECT COUNT(*) FROM provider_tracks").fetchone()[0]
                playlist_count = conn.execute("SELECT COUNT(*) FROM provider_playlists").fetchone()[0]
                source_count = conn.execute("SELECT COUNT(*) FROM track_sources").fetchone()[0]
                raw_count = conn.execute("SELECT COUNT(*) FROM provider_raw_responses").fetchone()[0]
                audit_count = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE event_type='provider_scan'"
                ).fetchone()[0]

            self.assertEqual(track_count, 1)
            self.assertEqual(playlist_count, 1)
            self.assertEqual(source_count, 1)
            self.assertEqual(raw_count, 2)
            self.assertEqual(audit_count, 2)

    def test_raw_response_does_not_store_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "musicark.db"
            initialize_database(db_path)
            provider = FakeYandexProvider(base_dir=Path(tmp))
            provider.scan_all(db_path)

            with closing(sqlite3.connect(db_path)) as conn:
                payload = conn.execute(
                    "SELECT payload_json FROM provider_raw_responses LIMIT 1"
                ).fetchone()[0]
            self.assertNotIn("YANDEX_MUSIC_TOKEN", payload)
            self.assertNotIn("Authorization", payload)
            decoded = json.loads(payload)
            self.assertEqual(decoded["provider"], "yandex_music")


if __name__ == "__main__":
    unittest.main()
