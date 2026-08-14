from __future__ import annotations

import json
import unittest

from musicark.providers.yandex_music_provider import YandexMusicProvider


class TrackDTO:
    def __init__(self, ident, title): self.id = ident; self.title = title
    def to_json(self): return json.dumps({"id": self.id, "title": self.title, "artists": [{"name": "Artist"}], "albums": [{"title": "Album"}]})


class PlaylistDTO:
    def __init__(self, kind, title, tracks): self.kind = kind; self.title = title; self.tracks = tracks; self.fetch_calls = 0
    def to_json(self): return json.dumps({"kind": self.kind, "title": self.title, "owner": {"name": "Tester"}, "track_count": len(self.tracks)})
    def fetch_tracks(self): self.fetch_calls += 1; return self.tracks


class Client:
    def __init__(self, playlists): self.playlists = playlists
    def users_playlists_list(self): return self.playlists


class Provider(YandexMusicProvider):
    def __init__(self, client): super().__init__(token="x"); self.client = client
    def _build_client(self): return self.client


class YandexProviderV03Tests(unittest.TestCase):
    def test_metadata_is_lazy_and_single_playlist_fetches_only_selected_contents(self):
        a = PlaylistDTO("10", "Rock", [TrackDTO("1", "One")]); b = PlaylistDTO("20", "Run", [TrackDTO("2", "Two")])
        provider = Provider(Client([a, b]))
        metadata = provider.list_playlist_metadata()
        self.assertEqual([item.external_id for item in metadata], ["10", "20"])
        self.assertEqual((a.fetch_calls, b.fetch_calls), (0, 0))
        selected, tracks = provider.get_playlist("20")
        self.assertEqual(selected.external_id, "20"); self.assertEqual([item.external_id for item in tracks], ["2"])
        self.assertEqual((a.fetch_calls, b.fetch_calls), (0, 1))


if __name__ == "__main__":
    unittest.main()
