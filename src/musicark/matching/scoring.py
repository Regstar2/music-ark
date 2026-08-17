"""Transparent candidate scoring for MusicArk v0.5."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any

from .models import MatchMethod, MatchScore, ScoredCandidate
from .normalize import normalize_artists, normalize_text, title_version_markers
from .policy import (
    ALBUM_WEIGHT,
    ARTIST_WEIGHT,
    DURATION_WEIGHT,
    FILENAME_FALLBACK_CAP,
    MISSING_ARTIST_CAP,
    TITLE_WEIGHT,
    VERSION_MISMATCH_CAP,
    WEAK_PRIMARY_SIGNAL_CAP,
)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _duration_score(provider_duration: Any, local_duration: Any) -> float | None:
    if provider_duration is None or local_duration is None:
        return None
    delta = abs(float(provider_duration) - float(local_duration))
    if delta <= 1.0:
        return 1.0
    if delta <= 2.0:
        return 0.95
    if delta <= 5.0:
        return 0.80
    if delta <= 10.0:
        return 0.45
    return 0.0


def _artist_score(provider_artists: tuple[str, ...], local_artists: tuple[str, ...]) -> float | None:
    if not provider_artists or not local_artists:
        return None
    provider_set = set(provider_artists)
    local_set = set(local_artists)
    intersection = len(provider_set & local_set)
    if intersection == 0:
        return 0.0
    return intersection / max(len(provider_set), len(local_set))


def _path_basename(path: str) -> str:
    """Handle both Windows and POSIX separators regardless of the host running tests."""
    return re.split(r"[\\/]", path)[-1]


def _strict_yandex_id_match(provider_id: str, external_id: str, path: str) -> bool:
    """Recognize the download convention without accepting arbitrary numbers in paths."""
    if provider_id != "yandex_music" or not external_id:
        return False
    name = _path_basename(path)
    pattern = re.compile(rf"^yandex[_-]{re.escape(external_id)}(?:\.[^.]+)?$", re.IGNORECASE)
    return bool(pattern.fullmatch(name))


def _trusted_embedded_identity(provider_id: str, external_id: str, local: dict[str, Any]) -> bool:
    """Trust only provenance already validated by the Local Metadata Reader gate."""
    return (
        provider_id == "yandex_music"
        and bool(external_id)
        and str(local.get("source_provider_id") or "") == provider_id
        and str(local.get("source_external_id") or "") == external_id
    )


class MatchScorer:
    """Score one already-bounded candidate pair; no storage or network access."""

    def score(self, provider: dict[str, Any], local: dict[str, Any]) -> ScoredCandidate:
        payload = provider["payload"]
        provider_id = str(provider["provider_id"])
        external_id = str(provider["external_id"])
        path = str(local.get("path") or "")

        if _trusted_embedded_identity(provider_id, external_id, local):
            score = MatchScore(
                title=1.0,
                artists=1.0,
                duration=1.0,
                album=1.0,
                filename=None,
                exact_id=1.0,
                final=1.0,
            )
            return ScoredCandidate(
                local_file_id=int(local["id"]),
                confidence=1.0,
                method=MatchMethod.EXACT_ID,
                breakdown=score.as_dict(),
                local=local,
            )

        if _strict_yandex_id_match(provider_id, external_id, path):
            score = MatchScore(
                title=1.0,
                artists=1.0,
                duration=1.0,
                album=1.0,
                filename=1.0,
                exact_id=1.0,
                final=0.995,
            )
            return ScoredCandidate(
                local_file_id=int(local["id"]),
                confidence=score.final,
                method=MatchMethod.EXACT_ID,
                breakdown=score.as_dict(),
                local=local,
            )

        provider_title = normalize_text(payload.get("title"))
        local_title_raw = str(local.get("title") or "")
        local_title = normalize_text(local_title_raw)
        filename_title = normalize_text(Path(_path_basename(path)).stem)
        tag_title_present = bool(local.get("tag_title_present", bool(local_title_raw)))

        title_score = _similarity(provider_title, local_title if local_title else filename_title)
        filename_score = _similarity(provider_title, filename_title) if filename_title else None
        provider_artists = normalize_artists(payload.get("artists") or ())
        local_artists = normalize_artists(local.get("artists") or ())
        artists_score = _artist_score(provider_artists, local_artists)
        duration_score = _duration_score(payload.get("duration_seconds"), local.get("duration_seconds"))

        provider_album = normalize_text(payload.get("album_title") or payload.get("album"))
        local_album = normalize_text(local.get("album"))
        album_score = _similarity(provider_album, local_album) if provider_album and local_album else None

        weighted = 0.0
        active = 0.0
        if provider_title and (local_title or filename_title):
            title_weight = TITLE_WEIGHT if tag_title_present else 0.40
            weighted += title_score * title_weight
            active += title_weight
        if artists_score is not None:
            weighted += artists_score * ARTIST_WEIGHT
            active += ARTIST_WEIGHT
        if duration_score is not None:
            weighted += duration_score * DURATION_WEIGHT
            active += DURATION_WEIGHT
        if album_score is not None:
            weighted += album_score * ALBUM_WEIGHT
            active += ALBUM_WEIGHT
        if not tag_title_present and filename_score is not None:
            weighted += filename_score * 0.10
            active += 0.10

        final = weighted / active if active else 0.0
        provider_markers = title_version_markers(payload.get("title"))
        local_markers = title_version_markers(local_title_raw)
        if provider_markers != local_markers and (provider_markers or local_markers):
            final = min(final, VERSION_MISMATCH_CAP)
        if (provider_artists and not local_artists) or (local_artists and not provider_artists):
            final = min(final, MISSING_ARTIST_CAP)
        if artists_score is not None and artists_score < 0.34:
            final = min(final, WEAK_PRIMARY_SIGNAL_CAP)
        if title_score < 0.55:
            final = min(final, WEAK_PRIMARY_SIGNAL_CAP)
        if not tag_title_present:
            final = min(final, FILENAME_FALLBACK_CAP)

        final = max(0.0, min(1.0, final))
        method = (
            MatchMethod.TITLE_ARTIST_DURATION
            if duration_score is not None and final >= 0.70
            else MatchMethod.TITLE_ARTIST
        )
        score = MatchScore(
            title=title_score,
            artists=artists_score,
            duration=duration_score,
            album=album_score,
            filename=filename_score,
            exact_id=0.0,
            final=final,
        )
        return ScoredCandidate(
            local_file_id=int(local["id"]),
            confidence=final,
            method=method,
            breakdown=score.as_dict(),
            local=local,
        )
