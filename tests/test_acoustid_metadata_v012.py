from __future__ import annotations

import unittest

import httpx

from musicark.external_metadata.acoustid_metadata import AcoustIdMetadataSource
from musicark.external_metadata.models import Confidence


class _Credentials:
    def get(self, name: str):
        return "client-key" if name == "acoustid_key" else None


class _Transport:
    def get(self, url: str, **kwargs):
        self.url = url
        self.kwargs = kwargs
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "results": [
                    {
                        "id": "acoustid-id",
                        "score": 0.99,
                        "recordings": [
                            {
                                "id": "recording-mbid",
                                "title": "Track Title",
                                "duration": 242,
                                "artists": [{"id": "artist-mbid", "name": "Artist"}],
                                "isrcs": ["USAAA0000001"],
                                "releasegroups": [
                                    {
                                        "id": "release-group-mbid",
                                        "title": "Album",
                                        "type": "Album",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            request=httpx.Request("GET", url),
        )


class AcoustIdMetadataV012Tests(unittest.TestCase):
    def test_rich_lookup_builds_candidate_without_musicbrainz_request(self) -> None:
        transport = _Transport()
        source = AcoustIdMetadataSource(transport, _Credentials())  # type: ignore[arg-type]

        items = source.lookup("fingerprint", 242)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source, "acoustid")
        self.assertEqual(item.source_track_id, "recording-mbid")
        self.assertEqual(item.fields["title"], "Track Title")
        self.assertEqual(item.fields["artists"], ["Artist"])
        self.assertEqual(item.fields["album"], "Album")
        self.assertEqual(item.fields["isrc"], "USAAA0000001")
        self.assertEqual(item.identities["acoustid"], "acoustid-id")
        self.assertEqual(item.identities["musicbrainz_recording_mbid"], "recording-mbid")
        self.assertEqual(item.identities["musicbrainz_release_group_mbid"], "release-group-mbid")
        self.assertEqual(item.confidence, Confidence.STRONG)
        self.assertIn("recordings releases releasegroups isrcs compress", transport.kwargs["params"]["meta"])


if __name__ == "__main__":
    unittest.main()
