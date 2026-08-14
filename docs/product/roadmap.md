# MusicArk Roadmap

```text
v0.1 — Yandex Likes MVP
v0.2 — Persistent Library
v0.3 — Yandex Library / Playlists
v0.4 — Local Library
v0.5 — Matching
v0.6 — Missing Tracks
v0.7 — Download
v0.8 — Sync
```

## v0.4 — Local Library

Index one or more user-selected folders, extract local audio metadata, persist roots and tracks, and incrementally reconcile new/changed/deleted files without modifying the underlying audio files.

## v0.5 — Matching

Compare Yandex and local structured metadata (`title`, `artists`, `album`, `duration`) and produce explicit matches/conflicts. v0.4 stores these fields without creating links prematurely.

## v0.6 — Missing Tracks

Identify provider tracks that do not have a sufficiently reliable local match.

## v0.7 — Download

Acquire explicitly requested missing tracks through supported download sources/workflows.

## v0.8 — Sync

Build controlled synchronization plans above matching and download results.

Standalone packaging/installer remains secondary infrastructure work and must not displace the product slices above.
