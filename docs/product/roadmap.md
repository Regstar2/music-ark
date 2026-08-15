# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                 complete
v0.2   — Persistent Library               complete
v0.3   — Yandex Library / Playlists       complete
v0.4   — Local Library                    complete
v0.5.0 — Identity Matching                complete
v0.5.1 — Variant / Altered Track Detection current
v0.6   — Missing Tracks                   planned
v0.7   — Download                         planned
v0.8   — Sync                             planned
```

## v0.5.0 — Identity Matching

Joins cached Yandex track identities with indexed Local Library files through bounded candidate generation, transparent scoring, ambiguity handling, and persistent manual decisions.

Primary quality metric: **precision of automatic matches**. When confidence or best-vs-second separation is insufficient, `CONFLICT`/`UNMATCHED` is preferred over a false positive.

## v0.5.1 — Variant / Altered Track Detection

Current product slice. It runs only after a v0.5 identity is `MATCHED` or manually accepted and asks a different question: whether the linked objects are the same recording/version.

Outputs are independent from identity:

```text
SAME
ALTERED
DIFFERENT_VERSION
UNCERTAIN
NOT_CHECKED
```

The milestone adds metadata variant markers, provider explicit evidence, strict exact-ID reference resolution, optional ffmpeg decoded-audio verification, bounded alignment, segment-level comparison, altered-region merging, caching/invalidation, SQLite schema 1.5.0, bridge commands, and Matching-page variant UI.

Primary quality metric: **avoid false SAME**. Unclear evidence should become `UNCERTAIN`, not an optimistic match.

v0.5.1 does not automatically download reference audio and does not use external fingerprint/matching services.

## v0.6 — Missing Tracks

Consume v0.5 identity results and expose provider tracks with no accepted local match. Variant verification does not replace the missing-track dataset.

## v0.7 — Download

Acquire explicitly requested missing tracks through supported download workflows. Download must not be pulled forward into matching or variant analysis.

## v0.8 — Sync

Build controlled synchronization plans above accepted matching and download results.

Standalone packaging/installer remains secondary infrastructure work and must not displace the product slices above.
