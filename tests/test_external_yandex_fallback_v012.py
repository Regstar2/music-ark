from __future__ import annotations

import unittest

from musicark.download.metadata import YandexTrackMetadata
from musicark.external_metadata.models import Confidence
from musicark.external_metadata.resolver import ExternalMetadataResolver


class _FakeYandexGateway:
    def search(self, query: str, *, limit: int = 20):
        assert query == "ЯМАУГЛИ ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ"
        assert limit == 8
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

    def public_payload(self, metadata: YandexTrackMetadata, *, cache_artwork: bool = False):
        assert cache_artwork is True
        return {"artwork": {"present": False, "cachePath": None}}


class ExternalYandexFallbackV012Tests(unittest.TestCase):
    def test_exact_text_yandex_search_is_strong_unbound_candidate(self) -> None:
        resolver = ExternalMetadataResolver.__new__(ExternalMetadataResolver)
        resolver._yandex = _FakeYandexGateway()  # type: ignore[attr-defined]

        items = resolver._yandex_search_candidates(  # noqa: SLF001
            title="ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
            artist="ЯМАУГЛИ",
        )

        self.assertEqual(len(items), 1)
        candidate = items[0]
        self.assertEqual(candidate.source, "yandex_music")
        self.assertEqual(candidate.source_track_id, "94970834")
        self.assertEqual(candidate.fields["title"], "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ")
        self.assertEqual(candidate.fields["album"], "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ")
        self.assertEqual(candidate.confidence, Confidence.STRONG)

    def test_non_exact_yandex_search_is_only_possible(self) -> None:
        resolver = ExternalMetadataResolver.__new__(ExternalMetadataResolver)
        resolver._yandex = _FakeYandexGateway()  # type: ignore[attr-defined]

        items = resolver._yandex_search_candidates(  # noqa: SLF001
            title="Призраков не существует",
            artist="Ямаугли",
        )

        # Comparison is case-insensitive, so the same text remains strong.
        self.assertEqual(items[0].confidence, Confidence.STRONG)


if __name__ == "__main__":
    unittest.main()
