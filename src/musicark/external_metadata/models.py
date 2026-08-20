"""Normalized contracts shared by external metadata sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Confidence(StrEnum):
    EXACT = "exact"
    STRONG = "strong"
    POSSIBLE = "possible"
    WEAK = "weak"
    AMBIGUOUS = "ambiguous"


class EvidenceType(StrEnum):
    ACOUSTID_FINGERPRINT = "ACOUSTID_FINGERPRINT"
    EXACT_RECORDING_MBID = "EXACT_RECORDING_MBID"
    EXACT_RELEASE_MBID = "EXACT_RELEASE_MBID"
    EXACT_ISRC = "EXACT_ISRC"
    EXACT_TITLE = "EXACT_TITLE"
    EXACT_ARTIST = "EXACT_ARTIST"
    DURATION_MATCH = "DURATION_MATCH"
    ALBUM_MATCH = "ALBUM_MATCH"
    YEAR_MATCH = "YEAR_MATCH"
    TRACK_NUMBER_MATCH = "TRACK_NUMBER_MATCH"


@dataclass(frozen=True, slots=True)
class MetadataEvidence:
    type: EvidenceType
    source: str
    value: str | float | int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "source": self.source, "value": self.value}


@dataclass(frozen=True, slots=True)
class ExternalArtworkCandidate:
    source: str
    cache_path: str | None = None
    source_url: str | None = None
    mime: str | None = None
    width: int | None = None
    height: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "cachePath": self.cache_path,
            "sourceUrl": self.source_url,
            "mime": self.mime,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class ExternalMetadataCandidate:
    source: str
    source_display_name: str
    source_track_id: str | None = None
    source_release_id: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    identities: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    evidence: tuple[MetadataEvidence, ...] = ()
    confidence: Confidence = Confidence.POSSIBLE
    artwork: ExternalArtworkCandidate | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceDisplayName": self.source_display_name,
            "sourceTrackId": self.source_track_id,
            "sourceReleaseId": self.source_release_id,
            "fields": dict(self.fields),
            "identities": dict(self.identities),
            "provenance": dict(self.provenance),
            "evidence": [item.as_dict() for item in self.evidence],
            "confidence": self.confidence.value,
            "artwork": self.artwork.as_dict() if self.artwork else {"source": self.source, "cachePath": None},
        }
