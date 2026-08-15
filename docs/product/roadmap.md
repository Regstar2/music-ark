# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                  complete
v0.2   — Persistent Library                complete
v0.3   — Yandex Library / Playlists        complete
v0.4   — Local Library                     complete
v0.5.0 — Identity Matching                 complete
v0.5.1 — Variant / Altered Track Detection complete
v0.6   — Missing Tracks / Coverage         current
v0.7   — Download                          planned
v0.8   — Sync                              planned
```

## v0.5.0 — Identity Matching

Joins cached Yandex track identities with indexed Local Library files through bounded candidate generation, transparent scoring, ambiguity handling, and persistent manual decisions.

Primary quality metric: **precision of automatic matches**. When confidence or best-vs-second separation is insufficient, `CONFLICT`/`UNMATCHED` is preferred over a false positive.

## v0.5.1 — Variant / Altered Track Detection

Runs only after a v0.5 identity is `MATCHED` or manually accepted and asks a different question: whether the linked objects are the same recording/version.

Outputs are independent from identity:

```text
SAME
ALTERED
DIFFERENT_VERSION
UNCERTAIN
NOT_CHECKED
```

The milestone adds metadata variant markers, provider explicit evidence, strict exact-ID reference resolution, optional ffmpeg decoded-audio verification, bounded alignment, segment-level comparison, altered-region merging, caching/invalidation, SQLite schema 1.5.0, bridge commands, and Matching-page variant UI.

Primary quality metric: **avoid false SAME**. Unclear evidence should become `UNCERTAIN`, not an optimistic result.

Current-code clarification: an explicit single-track `variant_run` may boundedly acquire one exact reference when needed. Batch remains restricted to already-resolvable references. The acquired reference is verification-only, not Local Library and not a general download workflow.

## v0.6 — Missing Tracks / Coverage

Current product slice. It consumes v0.5 identity results and active Yandex collection membership without rebuilding matching.

```text
current accepted MATCHED → COVERED
current UNMATCHED         → MISSING
CONFLICT / stale manual   → NEEDS_REVIEW
no/stale auto result      → NOT_ANALYZED
```

Variant status remains secondary. Global coverage deduplicates `(provider_id, external_id)` across Liked/playlists, supports collection scopes and SQL-backed list/search/filter/pagination, and lets the user persist `wanted/ignored` triage.

Primary quality metric: **do not lie about absence**. Conflict, unknown/stale state, different version, or reference cache must never be relabeled as Missing/Covered incorrectly.

Future v0.7 input is deliberately simple: `coverage_status = missing AND user_action = wanted`.

## v0.7 — Download

Acquire explicitly requested wanted+missing tracks through supported download workflows. Source selection and actual download must not be pulled forward into matching, variant analysis, or v0.6 coverage.

## v0.8 — Sync

Build controlled synchronization plans above accepted matching, coverage, and download results.

Standalone packaging/installer remains secondary infrastructure work and must not displace the product slices above.
