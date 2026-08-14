"""Metadata-level variant evidence kept separate from identity matching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from musicark.matching.normalize import normalize_text
from .models import VariantMarkers
from .policy import SEMANTIC_MARKERS, STRONG_VERSION_MARKERS


_MARKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (marker, re.compile(rf"(?:^|\b){re.escape(marker)}(?:\b|$)", re.IGNORECASE))
    for marker in sorted(SEMANTIC_MARKERS, key=len, reverse=True)
)


@dataclass(frozen=True, slots=True)
class MetadataVariantEvidence:
    provider: VariantMarkers
    local: VariantMarkers
    reasons: tuple[str, ...]
    metadata_score: float
    strong_version_mismatch: bool
    explicit_mismatch: bool
    duration_delta_seconds: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerMarkers": sorted(self.provider.markers),
            "localMarkers": sorted(self.local.markers),
            "providerExplicit": self.provider.explicit,
            "localExplicit": self.local.explicit,
            "reasons": list(self.reasons),
            "metadataScore": self.metadata_score,
            "strongVersionMismatch": self.strong_version_mismatch,
            "explicitMismatch": self.explicit_mismatch,
            "durationDeltaSeconds": self.duration_delta_seconds,
        }


def extract_variant_markers(*values: str | None) -> frozenset[str]:
    """Extract semantic version markers without deleting them from identity text."""
    text = " ".join(normalize_text(value) for value in values if value)
    found: set[str] = set()
    for marker, pattern in _MARKER_PATTERNS:
        if pattern.search(text):
            found.add(marker)
    # Preserve compound markers instead of double-counting their generic token.
    if "radio edit" in found or "radio version" in found:
        found.discard("edit")
    return frozenset(found)


def _explicit_from_local(local: dict[str, Any]) -> bool | None:
    metadata = local.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    for source in (local, metadata):
        if "explicit" in source and source.get("explicit") is not None:
            return bool(source.get("explicit"))
        if "content_warning" in source and source.get("content_warning") is not None:
            return bool(source.get("content_warning"))
    return None


class MetadataVariantDetector:
    """Generate conservative variant evidence from metadata only."""

    def analyze(self, provider: dict[str, Any], local: dict[str, Any]) -> MetadataVariantEvidence:
        provider_markers = extract_variant_markers(
            str(provider.get("title") or ""),
            str(provider.get("album_title") or provider.get("album") or ""),
        )
        local_path = str(local.get("path") or "")
        local_markers = extract_variant_markers(
            str(local.get("title") or ""),
            str(local.get("album") or ""),
            Path(local_path).stem if local_path else "",
        )
        provider_explicit = provider.get("explicit")
        if provider_explicit is not None:
            provider_explicit = bool(provider_explicit)
        local_explicit = _explicit_from_local(local)

        reasons: list[str] = []
        if provider_markers != local_markers:
            reasons.append("semantic_variant_marker_mismatch")
        strong_mismatch = bool((provider_markers ^ local_markers) & STRONG_VERSION_MARKERS)
        if strong_mismatch:
            reasons.append("strong_version_marker_mismatch")

        explicit_mismatch = (
            provider_explicit is not None
            and local_explicit is not None
            and provider_explicit != local_explicit
        )
        if explicit_mismatch:
            reasons.append("explicit_metadata_mismatch")

        provider_duration = provider.get("duration_seconds")
        local_duration = local.get("duration_seconds", local.get("durationSeconds"))
        duration_delta: float | None = None
        if provider_duration is not None and local_duration is not None:
            try:
                duration_delta = abs(float(provider_duration) - float(local_duration))
            except (TypeError, ValueError):
                duration_delta = None

        # This is evidence quality, not identity confidence and not the final class.
        score = 1.0
        if provider_markers != local_markers:
            score -= 0.30
        if explicit_mismatch:
            score -= 0.10
        if duration_delta is not None:
            score -= min(0.25, duration_delta / 60.0)
        score = max(0.0, min(1.0, score))

        return MetadataVariantEvidence(
            provider=VariantMarkers(provider_markers, provider_explicit),
            local=VariantMarkers(local_markers, local_explicit),
            reasons=tuple(reasons),
            metadata_score=score,
            strong_version_mismatch=strong_mismatch,
            explicit_mismatch=explicit_mismatch,
            duration_delta_seconds=duration_delta,
        )
