from __future__ import annotations

import unittest

from musicark.external_metadata.models import Confidence, ExternalMetadataCandidate
from musicark.external_metadata.yandex_first_resolver import YandexFirstExternalMetadataResolver


class _NoCache:
    def get(self, key):
        return None


class _PolicyResolver(YandexFirstExternalMetadataResolver):
    def __init__(self, *, yandex_items=None, acoustic_items=None, title="Track", artist="Artist") -> None:
        self._cache = _NoCache()
        self._title = title
        self._artist = artist
        self._yandex_items = list(yandex_items or [])
        self._acoustic_items = list(acoustic_items or [])
        self.yandex_calls = 0
        self.acoustic_calls = 0

    def _local(self, local_file_id):
        return {
            "id": local_file_id,
            "path": "C:/Music/track.mp3",
            "title": self._title,
            "artists": [self._artist] if self._artist else [],
            "album": "Album",
            "source_provider_id": None,
            "source_external_id": None,
        }

    @staticmethod
    def _file_key(local):
        return "fixture"

    def _yandex_search_candidates(self, *, title, artist, limit=8):
        self.yandex_calls += 1
        return list(self._yandex_items)

    def _acoustic_rescue(self, local_file_id, local, *, title, statuses):
        self.acoustic_calls += 1
        return list(self._acoustic_items), "recording-mbid" if self._acoustic_items else ""

    def _finish_resolution(self, cache_key, local_file_id, candidates, statuses, *, early_stop):
        return {
            "localFileId": local_file_id,
            "count": len(candidates),
            "items": [item.as_dict() for item in candidates],
            "sources": [],
            "diagnostics": statuses,
            "earlyStop": early_stop,
            "fromCache": False,
        }


def _candidate(source: str, confidence: Confidence, *, acoustic: bool = False) -> ExternalMetadataCandidate:
    identities = {"musicbrainz_recording_mbid": "recording-mbid"} if acoustic else {}
    return ExternalMetadataCandidate(
        source=source,
        source_display_name=source,
        source_track_id="id",
        fields={"title": "Track", "artists": ["Artist"]},
        identities=identities,
        confidence=confidence,
    )


class YandexFirstResolverPolicyTests(unittest.TestCase):
    def test_strong_yandex_hit_skips_fingerprint(self) -> None:
        resolver = _PolicyResolver(yandex_items=[_candidate("yandex_music", Confidence.STRONG)])

        payload = resolver.identify(1)

        self.assertEqual(resolver.yandex_calls, 1)
        self.assertEqual(resolver.acoustic_calls, 0)
        self.assertTrue(payload["earlyStop"])
        self.assertEqual(payload["items"][0]["source"], "yandex_music")

    def test_weak_yandex_hit_triggers_acoustic_rescue(self) -> None:
        resolver = _PolicyResolver(
            yandex_items=[_candidate("yandex_music", Confidence.POSSIBLE)],
            acoustic_items=[_candidate("acoustid", Confidence.STRONG, acoustic=True)],
        )

        payload = resolver.identify(1)

        self.assertEqual(resolver.yandex_calls, 1)
        self.assertEqual(resolver.acoustic_calls, 1)
        self.assertTrue(payload["earlyStop"])
        self.assertEqual({item["source"] for item in payload["items"]}, {"yandex_music", "acoustid"})

    def test_garbage_tags_use_acoustic_rescue_before_yandex(self) -> None:
        resolver = _PolicyResolver(
            title="Track",
            artist="drivemusic.me",
            yandex_items=[_candidate("yandex_music", Confidence.POSSIBLE)],
            acoustic_items=[_candidate("acoustid", Confidence.STRONG, acoustic=True)],
        )

        payload = resolver.identify(1)

        self.assertEqual(resolver.acoustic_calls, 1)
        self.assertEqual(resolver.yandex_calls, 0)
        self.assertTrue(payload["earlyStop"])
        self.assertEqual(payload["items"][0]["source"], "acoustid")

    def test_usable_tag_classification_rejects_placeholders(self) -> None:
        self.assertTrue(YandexFirstExternalMetadataResolver._usable_text_tags("Numb", "Linkin Park"))
        self.assertFalse(YandexFirstExternalMetadataResolver._usable_text_tags("Track", "drivemusic.me"))
        self.assertFalse(YandexFirstExternalMetadataResolver._usable_text_tags("", "Artist"))


if __name__ == "__main__":
    unittest.main()
