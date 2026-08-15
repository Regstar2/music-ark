"""Conservative, explainable classification policy for track variants."""

from __future__ import annotations

from .metadata import MetadataVariantEvidence
from .models import AudioComparison, VariantStatus
from .policy import (
    ALTERED_MAX_LOW_RATIO,
    ALTERED_MAX_REGION_COUNT,
    ALTERED_MAX_REGION_SECONDS,
    ALTERED_MIN_GLOBAL_SIMILARITY,
    DIFFERENT_VERSION_GLOBAL_SIMILARITY,
    DIFFERENT_VERSION_LOW_RATIO,
    DURATION_ABSOLUTE_DIFFERENCE_SECONDS,
    DURATION_RELATIVE_DIFFERENCE,
    SAME_GLOBAL_SIMILARITY,
    SAME_MAX_LOW_RATIO,
    SAME_MEDIAN_SIMILARITY,
)


class VariantClassifier:
    """Classify variant evidence without mixing it with v0.5 identity confidence."""

    def classify(
        self,
        metadata: MetadataVariantEvidence,
        audio: AudioComparison | None,
        *,
        provider_duration: float | None,
        local_duration: float | None,
        reference_available: bool,
        audio_available: bool,
    ) -> tuple[VariantStatus, tuple[str, ...]]:
        reasons = list(metadata.reasons)
        significant_duration = self._significant_duration_difference(
            provider_duration,
            local_duration,
        )
        if significant_duration:
            reasons.append("significant_duration_difference")

        # Strong semantic labels are useful evidence on their own. A track explicitly
        # labeled Live/Remix/Acoustic/etc. is not silently collapsed to SAME.
        if metadata.strong_version_mismatch:
            return VariantStatus.DIFFERENT_VERSION, tuple(dict.fromkeys(reasons))

        if audio is None:
            if metadata.explicit_mismatch:
                reasons.append("audio_evidence_required_for_censorship")
                return VariantStatus.UNCERTAIN, tuple(dict.fromkeys(reasons))
            if significant_duration:
                reasons.append("audio_evidence_missing")
                return VariantStatus.UNCERTAIN, tuple(dict.fromkeys(reasons))
            if metadata.provider.markers != metadata.local.markers:
                reasons.append("metadata_variant_mismatch_requires_audio")
                return VariantStatus.UNCERTAIN, tuple(dict.fromkeys(reasons))
            if not reference_available:
                reasons.append("reference_audio_missing")
            elif not audio_available:
                reasons.append("audio_decoder_unavailable")
            else:
                reasons.append("audio_not_checked")
            return VariantStatus.NOT_CHECKED, tuple(dict.fromkeys(reasons))

        longest_region = max(
            (region.end_seconds - region.start_seconds for region in audio.altered_regions),
            default=0.0,
        )
        has_regions = bool(audio.altered_regions)
        localized = (
            has_regions
            and audio.global_similarity >= ALTERED_MIN_GLOBAL_SIMILARITY
            and audio.low_similarity_window_ratio <= ALTERED_MAX_LOW_RATIO
            and longest_region <= ALTERED_MAX_REGION_SECONDS
            and len(audio.altered_regions) <= ALTERED_MAX_REGION_COUNT
        )

        if (
            not significant_duration
            and metadata.provider.markers == metadata.local.markers
            and not metadata.explicit_mismatch
            and audio.global_similarity >= SAME_GLOBAL_SIMILARITY
            and audio.median_window_similarity >= SAME_MEDIAN_SIMILARITY
            and audio.low_similarity_window_ratio <= SAME_MAX_LOW_RATIO
            and not has_regions
        ):
            reasons.append("decoded_audio_consistent")
            return VariantStatus.SAME, tuple(dict.fromkeys(reasons))

        if localized and not significant_duration:
            reasons.append("localized_audio_differences")
            # Explicit metadata is only one signal. We add this interpretation only
            # when decoded audio is otherwise the same recording and duration is close.
            if metadata.provider.explicit is True:
                reasons.append("possible_clean_or_censored_variant")
            return VariantStatus.ALTERED, tuple(dict.fromkeys(reasons))

        if significant_duration and (
            audio.global_similarity < SAME_GLOBAL_SIMILARITY
            or audio.low_similarity_window_ratio > SAME_MAX_LOW_RATIO
        ):
            return VariantStatus.DIFFERENT_VERSION, tuple(dict.fromkeys(reasons))

        if (
            audio.low_similarity_window_ratio >= DIFFERENT_VERSION_LOW_RATIO
            or audio.global_similarity <= DIFFERENT_VERSION_GLOBAL_SIMILARITY
        ):
            reasons.append("distributed_audio_differences")
            return VariantStatus.DIFFERENT_VERSION, tuple(dict.fromkeys(reasons))

        reasons.append("signals_near_classification_boundary")
        return VariantStatus.UNCERTAIN, tuple(dict.fromkeys(reasons))

    @staticmethod
    def _significant_duration_difference(
        provider_duration: float | None,
        local_duration: float | None,
    ) -> bool:
        if provider_duration is None or local_duration is None:
            return False
        try:
            provider_value = float(provider_duration)
            local_value = float(local_duration)
        except (TypeError, ValueError):
            return False
        if provider_value <= 0 or local_value <= 0:
            return False
        delta = abs(provider_value - local_value)
        relative = delta / max(provider_value, local_value)
        return (
            delta >= DURATION_ABSOLUTE_DIFFERENCE_SECONDS
            and relative >= DURATION_RELATIVE_DIFFERENCE
        )
