"""Matching domain models shared by the v0.5 pipeline and legacy callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MatchStatus(StrEnum):
    MATCHED = "matched"
    CONFLICT = "conflict"
    UNMATCHED = "unmatched"


class MatchMethod(StrEnum):
    """Method used to establish a provider/local relation."""

    EXACT_ID = "exact_id"
    TITLE_ARTIST_DURATION = "title_artist_duration"
    TITLE_ARTIST = "title_artist"
    AUTOMATIC = "automatic"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class Track:
    """Canonical music track entity retained from the legacy matching layer."""

    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_seconds: float | None
    normalized_title: str
    normalized_artists: tuple[str, ...]
    id: int | None = None


@dataclass(frozen=True, slots=True)
class TrackLink:
    """Confirmed link between canonical/provider/local identities."""

    track_id: int
    source_provider_id: str
    source_external_id: str
    local_file_id: int
    confidence: float
    match_method: MatchMethod
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MatchConflict:
    """Potential match that requires manual confirmation."""

    source_provider_id: str
    source_external_id: str
    local_file_id: int
    confidence: float
    reason: str
    score_breakdown: dict[str, float] = field(default_factory=dict)
    candidate_rank: int = 1


@dataclass(frozen=True, slots=True)
class MatchScore:
    """Transparent score components for one provider/local candidate pair."""

    title: float
    artists: float | None
    duration: float | None
    album: float | None
    filename: float | None
    exact_id: float
    final: float

    def as_dict(self) -> dict[str, float | None]:
        return {
            "title": round(self.title, 6),
            "artists": None if self.artists is None else round(self.artists, 6),
            "duration": None if self.duration is None else round(self.duration, 6),
            "album": None if self.album is None else round(self.album, 6),
            "filename": None if self.filename is None else round(self.filename, 6),
            "exact_id": round(self.exact_id, 6),
            "final": round(self.final, 6),
        }


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    local_file_id: int
    confidence: float
    method: MatchMethod
    breakdown: dict[str, float | None]
    local: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MatchDecision:
    provider_id: str
    external_id: str
    provider_payload: dict[str, Any]
    provider_fingerprint: str
    local_fingerprint: str
    status: MatchStatus
    local_file_id: int | None
    confidence: float
    method: MatchMethod
    breakdown: dict[str, float | None]
    reason: str
    candidates: tuple[ScoredCandidate, ...] = ()
