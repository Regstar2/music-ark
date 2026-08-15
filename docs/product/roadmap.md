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

v0.5.1 keeps variant state independent from identity. Its current implementation may acquire one exact reference during an explicit single-track verification; that bounded cache is verification-only and is not Local Library or Missing Tracks download.

v0.6 derives honest coverage from current v0.5 identity state. Only current `UNMATCHED` is `missing`; conflict/stale/not-analyzed remain distinct. `missing + wanted` is the future v0.7 input.
