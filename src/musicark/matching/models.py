"""Matching and canonical library models for v0.7."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MatchMethod(StrEnum):
    """Method used to establish a source/file match."""

    EXACT_ID = "exact_id"
    TITLE_ARTIST_DURATION = "title_artist_duration"
    TITLE_ARTIST = "title_artist"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class Track:
    """Canonical music track entity."""

    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_seconds: float | None
    normalized_title: str
    normalized_artists: tuple[str, ...]
    id: int | None = None


@dataclass(frozen=True, slots=True)
class TrackLink:
    """Link between canonical track, provider source, and local file."""

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
