"""User-facing automatic resolver with noisy-tag cleanup.

The policy remains Yandex-first. Before a catalog lookup, obvious advertising
noise from downloaded tags is removed. AcoustID remains a rescue mechanism, not
the first choice for otherwise usable text metadata.
"""

from __future__ import annotations

from .lookup_cleanup import sanitize_lookup_artist, sanitize_lookup_title
from .models import Confidence, ExternalMetadataCandidate
from .yandex_first_resolver import YandexFirstExternalMetadataResolver


class AutomaticExternalMetadataResolver(YandexFirstExternalMetadataResolver):
    """Yandex-first resolver that cleans lookup text conservatively."""

    _CACHE_POLICY_VERSION = "yandex-first-clean-v2"

    @staticmethod
    def _dedupe(items: list[ExternalMetadataCandidate]) -> list[ExternalMetadataCandidate]:
        result: list[ExternalMetadataCandidate] = []
        seen: set[tuple[str, str | None, str | None]] = set()
        for item in items:
            key = (item.source, item.source_track_id, item.source_release_id)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _yandex_search_candidates(
        self,
        *,
        title: str,
        artist: str,
        limit: int = 8,
    ) -> list[ExternalMetadataCandidate]:
        clean_title = sanitize_lookup_title(title)
        clean_artist = sanitize_lookup_artist(artist)
        if not clean_title:
            return []

        # First try the most precise cleaned Artist + Title lookup.
        items = super()._yandex_search_candidates(
            title=clean_title,
            artist=clean_artist,
            limit=limit,
        )
        if any(item.confidence in {Confidence.EXACT, Confidence.STRONG} for item in items):
            return self._dedupe(items)

        # Artist tags are often contaminated independently from Title. A second,
        # cheap title-only search is preferable to immediately fingerprinting the
        # whole audio file. Do not issue it when the first lookup was already
        # title-only.
        if clean_artist:
            title_only = super()._yandex_search_candidates(
                title=clean_title,
                artist="",
                limit=limit,
            )
            items.extend(title_only)

        return self._dedupe(items)
