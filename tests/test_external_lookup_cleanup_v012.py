from __future__ import annotations

import unittest

from musicark.download.metadata import YandexTrackMetadata
from musicark.external_metadata.automatic_resolver import AutomaticExternalMetadataResolver
from musicark.external_metadata.lookup_cleanup import sanitize_lookup_title
from musicark.external_metadata.models import Confidence


class _FakeYandexGateway:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, *, limit: int = 20):
        self.queries.append(query)
        if query.casefold() == "ямаугли призраков не существует".casefold():
            return [
                YandexTrackMetadata(
                    provider_id="yandex_music",
                    external_id="94970834",
                    title="ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                    artists=("ЯМАУГЛИ",),
                    album_id="album-1",
                    album_title="ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                    release_year=2021,
                    duration_seconds=151.0,
                )
            ]
        return []

    def public_payload(self, metadata: YandexTrackMetadata, *, cache_artwork: bool = False):
        return {"artwork": {"present": False, "cachePath": None}}


class ExternalLookupCleanupV012Tests(unittest.TestCase):
    def test_drive_music_bracket_prefix_is_removed(self) -> None:
        self.assertEqual(
            sanitize_lookup_title("[drive-music] ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ"),
            "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
        )

    def test_semantic_version_marker_is_preserved(self) -> None:
        self.assertEqual(
            sanitize_lookup_title("Song Name [Live]"),
            "Song Name [Live]",
        )

    def test_yandex_lookup_uses_cleaned_title_before_acoustic_rescue(self) -> None:
        resolver = AutomaticExternalMetadataResolver.__new__(AutomaticExternalMetadataResolver)
        gateway = _FakeYandexGateway()
        resolver._yandex = gateway  # type: ignore[attr-defined]

        items = resolver._yandex_search_candidates(  # noqa: SLF001
            title="[drive-music] ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
            artist="ЯМАУГЛИ",
        )

        self.assertTrue(gateway.queries)
        self.assertEqual(gateway.queries[0], "ЯМАУГЛИ ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_track_id, "94970834")
        self.assertEqual(items[0].confidence, Confidence.STRONG)


if __name__ == "__main__":
    unittest.main()
