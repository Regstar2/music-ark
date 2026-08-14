"""Domain models for v0.5.1 track variant verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VariantStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    SAME = "same"
    ALTERED = "altered"
    DIFFERENT_VERSION = "different_version"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class VariantMarkers:
    markers: frozenset[str] = frozenset()
    explicit: bool | None = None


@dataclass(frozen=True, slots=True)
class ReferenceAudio:
    path: Path
    provider_id: str
    external_id: str


@dataclass(frozen=True, slots=True)
class DecodedAudio:
    samples: tuple[int, ...]
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return len(self.samples) / self.sample_rate


@dataclass(frozen=True, slots=True)
class AlteredRegion:
    start_seconds: float
    end_seconds: float
    mean_similarity: float
    minimum_similarity: float

    def as_dict(self) -> dict[str, float]:
        return {
            "startSeconds": round(self.start_seconds, 3),
            "endSeconds": round(self.end_seconds, 3),
            "meanSimilarity": round(self.mean_similarity, 6),
            "minimumSimilarity": round(self.minimum_similarity, 6),
        }


@dataclass(frozen=True, slots=True)
class AudioComparison:
    alignment_offset_seconds: float
    alignment_confidence: float
    global_similarity: float
    median_window_similarity: float
    low_similarity_window_ratio: float
    altered_regions: tuple[AlteredRegion, ...] = ()
    window_count: int = 0


@dataclass(frozen=True, slots=True)
class VariantResult:
    provider_id: str
    external_id: str
    local_file_id: int
    status: VariantStatus
    reasons: tuple[str, ...] = ()
    audio_similarity: float | None = None
    metadata_score: float | None = None
    altered_regions: tuple[AlteredRegion, ...] = ()
    provider_variant_fingerprint: str = ""
    local_audio_fingerprint: str = ""
    reference_audio_fingerprint: str = ""
    analyzer_version: int = 1
    reference_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "externalId": self.external_id,
            "localFileId": self.local_file_id,
            "status": self.status.value,
            "variantStatus": self.status.value,
            "variantReasons": list(self.reasons),
            "audioSimilarity": self.audio_similarity,
            "metadataScore": self.metadata_score,
            "alteredSegments": [region.as_dict() for region in self.altered_regions],
            "providerVariantFingerprint": self.provider_variant_fingerprint,
            "localAudioFingerprint": self.local_audio_fingerprint,
            "referenceAudioFingerprint": self.reference_audio_fingerprint,
            "analyzerVersion": self.analyzer_version,
            "referencePath": self.reference_path,
            "metadata": dict(self.metadata),
        }
