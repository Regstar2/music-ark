"""Policy constants for MusicArk v0.5 matching.

Precision of automatic matches is intentionally favored over recall.
"""

# v2 recognizes MusicArk's [yandex_<externalId>] filename provenance and gives
# unique exact provider identity precedence over metadata-only candidates.
# Bumping the matcher version intentionally invalidates cached v1 decisions so
# existing ambiguous results are recalculated under the corrected policy.
MATCHER_VERSION = 2
CANDIDATE_LIMIT = 40
PERSISTED_CONFLICT_CANDIDATES = 5

AUTO_MATCH_THRESHOLD = 0.90
CONFLICT_THRESHOLD = 0.70
AMBIGUITY_MARGIN = 0.04

TITLE_WEIGHT = 0.50
ARTIST_WEIGHT = 0.30
DURATION_WEIGHT = 0.15
ALBUM_WEIGHT = 0.05

# Conservative caps for cases where one strong textual signal would otherwise dominate.
MISSING_ARTIST_CAP = 0.84
VERSION_MISMATCH_CAP = 0.84
WEAK_PRIMARY_SIGNAL_CAP = 0.69
FILENAME_FALLBACK_CAP = 0.88
