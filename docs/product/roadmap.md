# MusicArk Roadmap

```text
v0.1 — Yandex Likes MVP             complete
v0.2 — Persistent Library           complete
v0.3 — Yandex Library / Playlists   complete
v0.4 — Local Library                complete
v0.5 — Matching                     current
v0.6 — Missing Tracks               planned
v0.7 — Download                     planned
v0.8 — Sync                         planned
```

## v0.5 — Matching

Current product slice. It joins cached Yandex track identities with indexed Local Library files through bounded candidate generation, transparent scoring, ambiguity handling, and persistent manual decisions.

Primary quality metric: **precision of automatic matches**. When confidence or best-vs-second separation is insufficient, `conflict`/`unmatched` is preferred over a false positive.

## v0.6 — Missing Tracks

Consume v0.5 results and expose provider tracks with no accepted local match. v0.6 owns the product workflow around missing content; v0.5 only creates the reliable dataset.

## v0.7 — Download

Acquire explicitly requested missing tracks through supported download workflows. Download must not be pulled forward into matching.

## v0.8 — Sync

Build controlled synchronization plans above accepted matching and download results.

Standalone packaging/installer remains secondary infrastructure work and must not displace the product slices above.
