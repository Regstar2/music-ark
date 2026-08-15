# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                  complete
v0.2   — Persistent Library                complete
v0.3   — Yandex Library / Playlists        complete
v0.4   — Local Library                     complete
v0.5.0 — Identity Matching                 complete
v0.5.1 — Variant / Altered Track Detection complete
v0.6   — Missing Tracks / Coverage         complete
v0.7   — Download                          current
v0.8   — Sync                              planned
```

## v0.5.0 — Identity Matching

Joins cached Yandex track identities with indexed Local Library files through bounded candidate generation, transparent scoring, ambiguity handling, and persistent manual decisions. Precision of automatic matches remains more important than recall.

## v0.5.1 — Variant / Altered Track Detection

Runs only after an identity is accepted and independently asks whether the linked objects are the same recording/version. Results remain `SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED`. Exact reference acquisition is verification-only and never counts as Local Library coverage.

## v0.6 — Missing Tracks / Coverage

Consumes authoritative matching state and active Yandex membership to derive `covered / missing / needs_review / not_analyzed`, with persistent `wanted / ignored / unreviewed` triage. Variant remains secondary. Conflict, stale state and reference cache never masquerade as Missing or Covered.

## v0.7 — Download

Current product slice. The only ordinary input is:

```text
coverage_status = missing
AND user_action = wanted
```

v0.7 adds a persistent provider-based queue around the existing authenticated Yandex Music acquisition backend. The target is a selected Local Library root with a managed `MusicArk` child. Transfers are streamed to `.part`, report real byte progress when `Content-Length` exists, support cooperative cancellation, and are intentionally sequential in the baseline implementation.

A task is not successful at HTTP completion. It must produce a parseable file, index it through the normal v0.4 Local Library pipeline with a real `library_root_id`, persist an exact accepted provider/local identity link, and make Coverage return `covered`. Exact acquisition identity does not manufacture a Variant result.

Reference cache and user Download Library stay separate. Credentials come from the existing secure credential abstraction; token/direct URLs are not queue metadata. v0.7 adds no YouTube/VK/torrent/web-search fallback and no DRM/access bypass.

Primary quality metric: **the downloaded track must become a normal covered Local Library identity, or the task must not be marked completed**.

## v0.8 — Sync

Build controlled synchronization plans above accepted matching, coverage, and download results. v0.7 performs post-download indexing/linking/coverage refresh only and does not pre-build the sync planner.

Standalone packaging/installer remains secondary infrastructure work and must not displace the product slices above.
