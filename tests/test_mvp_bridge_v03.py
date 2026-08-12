from __future__ import annotations

import unittest

from musicark.mvp_bridge import _error_payload, library_refresh, liked_refresh, playlist, playlist_refresh, playlists
from musicark.providers.yandex_music_provider import YandexMusicError


class FakeService:
    def liked_refresh(self): return {"liked": {"source": "network"}}
    def playlists(self): return {"playlists": {"items": [{"externalId": "10"}]}}
    def playlist(self, external_id): return {"playlist": {"externalId": external_id}, "collection": {"source": "cache"}}
    def playlist_refresh(self, external_id): return {"playlist": {"externalId": external_id}, "collection": {"source": "network"}}
    def library_refresh(self): return {"liked": {"source": "network"}, "playlists": {"source": "network"}}


class BridgeV03Tests(unittest.TestCase):
    def test_new_library_commands_delegate(self):
        service = FakeService()
        self.assertEqual(liked_refresh(service)["liked"]["source"], "network")
        self.assertEqual(playlists(service)["playlists"]["items"][0]["externalId"], "10")
        self.assertEqual(playlist("10", service)["collection"]["source"], "cache")
        self.assertEqual(playlist_refresh("10", service)["collection"]["source"], "network")
        self.assertEqual(library_refresh(service)["playlists"]["source"], "network")
    def test_provider_error_is_normalized(self):
        payload = _error_payload(YandexMusicError("offline"))
        self.assertEqual(payload["error"]["code"], "yandex_request_failed")
        self.assertEqual(payload["error"]["message"], "offline")


if __name__ == "__main__":
    unittest.main()
