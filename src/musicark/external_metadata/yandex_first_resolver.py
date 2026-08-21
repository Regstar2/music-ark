"""Yandex-first resolver policy for the user-facing automatic metadata flow.

MusicArk is a Yandex Music companion, not a generic tagger.  When a local file
already has usable artist/title tags, the fastest and most relevant source is
therefore Yandex Music.  Acoustic fingerprinting is a rescue mechanism for
missing/garbled tags or when Yandex cannot produce a strong catalog match.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fingerprint import FingerprintError
from .models import Confidence, ExternalMetadataCandidate
from .resolver import ExternalMetadataResolver


class YandexFirstExternalMetadataResolver(ExternalMetadataResolver):
    """User-facing resolver policy: Yandex first, audio fingerprint as rescue."""

    _GARBAGE = {
        "",
        "-",
        "—",
        "unknown",
        "unknown artist",
        "unknown title",
        "track",
        "audio",
        "drivemusic.me",
    }
    _CACHE_POLICY_VERSION = "yandex-first-v1"

    @classmethod
    def _usable_text_tags(cls, title: str, artist: str) -> bool:
        title_key = title.strip().casefold()
        artist_key = artist.strip().casefold()
        if title_key in cls._GARBAGE or artist_key in cls._GARBAGE:
            return False
        # Very short placeholder-shaped values are not useful enough to skip
        # acoustic rescue.
        return len(title_key) >= 2 and len(artist_key) >= 2

    @staticmethod
    def _has_strong(items: list[ExternalMetadataCandidate]) -> bool:
        return any(item.confidence in {Confidence.EXACT, Confidence.STRONG} for item in items)

    def _acoustic_rescue(
        self,
        local_file_id: int,
        local: dict[str, Any],
        *,
        title: str,
        statuses: list[dict[str, str]],
    ) -> tuple[list[ExternalMetadataCandidate], str]:
        """Identify a recording from audio without making it the normal fast path."""
        fingerprint_items: list[ExternalMetadataCandidate] = []
        try:
            fp = self._fingerprints.fingerprint(int(local_file_id), Path(str(local["path"])))
            fingerprint_items = self._call(
                statuses,
                "acoustid",
                lambda: self._acoustid.lookup(fp.fingerprint, fp.duration),
            ) or []
            fingerprint_items = self._with_artwork(fingerprint_items, statuses)
        except FingerprintError as exc:
            statuses.append(self._status("acoustid", "fingerprint_unavailable", str(exc)))
            return [], ""

        recording_mbid = self._recording_mbid(fingerprint_items)
        if recording_mbid and not self._strong_fingerprint_result(fingerprint_items):
            enriched = self._call(
                statuses,
                "listenbrainz_metadata",
                lambda: self._listenbrainz.recording(recording_mbid, fallback_title=title),
            ) or []
            if not enriched:
                # Direct MusicBrainz remains best-effort only.  Failure here does
                # not invalidate the AcoustID candidates already obtained.
                enriched = self._call(
                    statuses,
                    "musicbrainz",
                    lambda: self._musicbrainz.recording(recording_mbid),
                ) or []
            fingerprint_items.extend(self._with_artwork(enriched, statuses))

        return fingerprint_items, recording_mbid

    def identify(self, local_file_id: int, *, continue_search: bool = False) -> dict[str, Any]:
        local = self._local(local_file_id)
        resolution_key = (
            f"resolve:{self._CACHE_POLICY_VERSION}:{int(local_file_id)}:"
            f"{self._file_key(local)}:{1 if continue_search else 0}"
        )
        cached = self._cache.get(resolution_key)
        if cached is not None and cached[0] is False and isinstance(cached[1], dict):
            payload = dict(cached[1])
            payload["fromCache"] = True
            return payload

        statuses: list[dict[str, str]] = []
        candidates: list[ExternalMetadataCandidate] = []

        raw_title = str(local.get("title") or "").strip()
        title = raw_title or Path(str(local["path"])).stem.strip()
        artists = [str(item).strip() for item in local.get("artists") or [] if str(item).strip()]
        artist = artists[0] if artists else ""
        album = str(local.get("album") or "").strip()

        # A trusted exact Yandex identity is still the strongest possible source.
        if local.get("source_provider_id") == "yandex_music" and local.get("source_external_id"):
            try:
                metadata = self._yandex.get(str(local["source_external_id"]))
                public = self._yandex.public_payload(metadata, cache_artwork=True)
                candidates.append(self._yandex_candidate(metadata, public))
                statuses.append(self._status("yandex_music", "ok"))
                if not continue_search:
                    return self._finish_resolution(
                        resolution_key, local_file_id, candidates, statuses, early_stop=True
                    )
            except Exception as exc:  # noqa: BLE001 - resolver isolates source failures.
                statuses.append(self._status("yandex_music", "unavailable", str(exc)))

        usable_tags = self._usable_text_tags(raw_title, artist)
        yandex_items: list[ExternalMetadataCandidate] = []

        # Normal path: usable tags -> Yandex first.  A strong Yandex hit finishes
        # immediately; fingerprinting is not even started.
        if usable_tags:
            yandex_items = self._call(
                statuses,
                "yandex_music_search",
                lambda: self._yandex_search_candidates(title=raw_title, artist=artist),
            ) or []
            candidates.extend(yandex_items)
            if self._has_strong(yandex_items) and not continue_search:
                return self._finish_resolution(
                    resolution_key, local_file_id, candidates, statuses, early_stop=True
                )

        # Rescue path: bad/missing tags, no Yandex result, weak Yandex result, or an
        # explicit request for more alternatives.
        needs_acoustic_rescue = continue_search or not usable_tags or not self._has_strong(yandex_items)
        recording_mbid = ""
        if needs_acoustic_rescue:
            fingerprint_items, recording_mbid = self._acoustic_rescue(
                local_file_id,
                local,
                title=title,
                statuses=statuses,
            )
            candidates.extend(fingerprint_items)
            if self._strong_fingerprint_result(fingerprint_items) and not continue_search:
                return self._finish_resolution(
                    resolution_key, local_file_id, candidates, statuses, early_stop=True
                )

        # If tags were too poor to try Yandex first, use any recovered/filename text
        # after the acoustic attempt.  This stays a candidate-only search: no bind.
        if not usable_tags and title and not yandex_items:
            yandex_items = self._call(
                statuses,
                "yandex_music_search",
                lambda: self._yandex_search_candidates(title=title, artist=artist),
            ) or []
            candidates.extend(yandex_items)
            if self._has_strong(yandex_items) and not continue_search:
                return self._finish_resolution(
                    resolution_key, local_file_id, candidates, statuses, early_stop=True
                )

        # If we already have any useful Yandex/AcoustID candidate in normal mode,
        # show it immediately instead of waiting on slow optional services.  The
        # user can explicitly request "more alternatives" to continue.
        if candidates and not continue_search:
            return self._finish_resolution(
                resolution_key, local_file_id, candidates, statuses, early_stop=False
            )

        # Optional enrichment/fallbacks are reached only when the primary paths did
        # not produce a candidate or when the user explicitly asks for alternatives.
        audiodb_tried = False
        if title and artist and not candidates:
            audiodb_tried = True
            candidates.extend(
                self._call(
                    statuses,
                    "theaudiodb",
                    lambda: self._audiodb.search(title=title, artist=artist),
                )
                or []
            )

        if title and (continue_search or not candidates):
            mb_items = self._call(
                statuses,
                "musicbrainz",
                lambda: self._musicbrainz.search(title=title, artist=artist, album=album),
            ) or []
            if not mb_items and artist:
                mb_items = self._call(
                    statuses,
                    "listenbrainz_mapper",
                    lambda: self._listenbrainz.search(title=title, artist=artist, album=album),
                ) or []
            candidates.extend(self._with_artwork(mb_items, statuses))

        if continue_search or not candidates:
            candidates.extend(
                self._call(
                    statuses,
                    "discogs",
                    lambda: self._discogs.search(title=title, artist=artist, album=album),
                )
                or []
            )
            if title and artist and not audiodb_tried:
                candidates.extend(
                    self._call(
                        statuses,
                        "theaudiodb",
                        lambda: self._audiodb.search(title=title, artist=artist),
                    )
                    or []
                )
            candidates.extend(
                self._call(
                    statuses,
                    "lastfm",
                    lambda: self._lastfm.search(
                        title=title,
                        artist=artist,
                        recording_mbid=recording_mbid,
                    ),
                )
                or []
            )

        return self._finish_resolution(
            resolution_key, local_file_id, candidates, statuses, early_stop=False
        )
