"""Domain enums for Library Coverage.

Identity coverage, recording-variant verification, and the user's triage action are
deliberately separate dimensions.
"""

from __future__ import annotations

from enum import Enum


class CoverageStatus(str, Enum):
    COVERED = "covered"
    MISSING = "missing"
    NEEDS_REVIEW = "needs_review"
    NOT_ANALYZED = "not_analyzed"


class ProviderTrackAction(str, Enum):
    WANTED = "wanted"
    IGNORED = "ignored"
    UNREVIEWED = "unreviewed"
