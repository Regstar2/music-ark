"""Centralized thresholds for v0.5.1 variant/audio analysis."""

from __future__ import annotations

ANALYZER_VERSION = 1
SAMPLE_RATE = 11025
WINDOW_SECONDS = 2.0
HOP_SECONDS = 0.75
ALIGNMENT_FRAME_SECONDS = 0.25
MAX_ALIGNMENT_OFFSET_SECONDS = 15.0
DECODE_TIMEOUT_SECONDS = 180.0
MIN_AUDIO_SECONDS = 12.0

LOW_SIMILARITY_THRESHOLD = 0.78
STRONG_DIVERGENCE_THRESHOLD = 0.45
SAME_GLOBAL_SIMILARITY = 0.94
SAME_MEDIAN_SIMILARITY = 0.95
SAME_MAX_LOW_RATIO = 0.06
ALTERED_MIN_GLOBAL_SIMILARITY = 0.86
ALTERED_MAX_LOW_RATIO = 0.20
ALTERED_MAX_REGION_SECONDS = 10.0
ALTERED_MAX_REGION_COUNT = 6
DIFFERENT_VERSION_LOW_RATIO = 0.28
DIFFERENT_VERSION_GLOBAL_SIMILARITY = 0.76
DURATION_ABSOLUTE_DIFFERENCE_SECONDS = 10.0
DURATION_RELATIVE_DIFFERENCE = 0.07
ALIGNMENT_MIN_CONFIDENCE = 0.20

SEMANTIC_MARKERS = frozenset(
    {
        "live",
        "remix",
        "mix",
        "acoustic",
        "instrumental",
        "remaster",
        "remastered",
        "radio edit",
        "radio version",
        "edit",
        "extended",
        "demo",
        "clean",
        "explicit",
        "censored",
        "uncensored",
    }
)

STRONG_VERSION_MARKERS = frozenset(
    {
        "live",
        "remix",
        "acoustic",
        "instrumental",
        "radio edit",
        "radio version",
        "extended",
        "demo",
    }
)
