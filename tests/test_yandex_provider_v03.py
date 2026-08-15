from __future__ import annotations

import json
import unittest

from musicark.providers.yandex_music_provider import YandexMusicProvider


class TrackDTO:
    def __init__(self, ident, title, artist="Artist"):
        self.id = ident
        self.title = title
        self.artist = artist

    def to_json(self):
        return json.dumps({
            "id": self.id,
            "title": self.title,
            "artists": [{"name": self.artist}],
            "albums": [{"title": "Album"}],
        })


class TrackShortDTO:
    def __init__(self, ident, album_id=None):
        self.id = ident
        self.album_id = album_id
        self.track = None

    @property
    def track_id(self):
        return f"{self.id}:{self.album_id}" if self.album_id else str(self.id)

    def to_json(self):
        return json.dumps({"id": self.id, "album_id": self.album_id})


class PlaylistDTO:
    def __init__(self, kind, title, tracks):
        self.kind = kind
        self.title = title
        self.tracks = tracks
        self.fetch_calls = 0

    def to_json(self):
        return json.dumps({
            "kind": self.kind,
            "title": self.title,
            "owner": {"name": "Tester"},
            "track_count": len(self.tracks),
        })

    def fetch_tracks(self):
        self.fetch_calls += 1
        return self.tracks


class Client:
    def __init__(self, playlists, full_tracks=None):
        self.playlists = playlists
        self.full_tracks = full_tracks or {}
        self.track_batch_calls = []

    def users_playlists_list(self):
        return self.playlists

    def tracks(self, track_ids):
        ids = list(track_ids) if not isinstance(track_ids, (str, int)) else [track_ids]
        self.track_batch_calls.append(ids)
        result = []
        for track_id in ids:
            base_id = str(track_id).split(":", 1)[0]
            track = self.full_tracks.get(base_id)
            if track is not None:
                result.append(track)
        return result


class Provider(YandexMusicProvider):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def _build_client(self):
        return self.client


class YandexProviderV03Tests(unittest.TestCase):
    def test_metadata_is_lazy_and_single_playlist_fetches_only_selected_contents(self):
        a = PlaylistDTO("10", "Rock", [TrackDTO("1", "One")])
        b = PlaylistDTO("20", "Run", [TrackDTO("2", "Two")])
        client = Client([a, b])
        provider = Provider(client)
        metadata = provider.list_playlist_metadata()
        self.assertEqual([item.external_id for item in metadata], ["10", "20"])
        self.assertEqual((a.fetch_calls, b.fetch_calls), (0, 0))
        selected, tracks = provider.get_playlist("20")
        self.assertEqual(selected.external_id, "20")
        self.assertEqual([item.external_id for item in tracks], ["2"])
        self.assertEqual((a.fetch_calls, b.fetch_calls), (0, 1))
        self.assertEqual(client.track_batch_calls, [])

    def test_playlist_trackshorts_are_hydrated_in_one_batch_and_keep_order_and_duplicates(self):
        playlist = PlaylistDTO(
            "20",
            "Run",
            [TrackShortDTO("2", "a2"), TrackShortDTO("1", "a1"), TrackShortDTO("2", "a2")],
        )
        client = Client(
            [playlist],
            full_tracks={
                "1": TrackDTO("1", "One", "First Artist"),
                "2": TrackDTO("2", "Two", "Second Artist"),
            },
        )
        provider = Provider(client)
        selected, tracks = provider.get_playlist("20")
        self.assertEqual(selected.external_id, "20")
        self.assertEqual([item.external_id for item in tracks], ["2", "1", "2"])
        self.assertEqual([item.title for item in tracks], ["Two", "One", "Two"])
        self.assertEqual(client.track_batch_calls, [["2:a2", "1:a1"]])


if __name__ == "__main__":
    unittest.main()
