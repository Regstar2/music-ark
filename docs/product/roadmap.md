# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                              complete
v0.2   — Persistent Library                            complete
v0.3   — Yandex Library / Playlists                    complete
v0.4   — Local Library                                 complete
v0.5.0 — Identity Matching                             complete
v0.5.1 — Variant / Altered Track Detection             complete
v0.6   — Missing Tracks / Coverage                     complete
v0.7   — Download + Local Playback                     complete
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata Import current code baseline
next   — stabilization / TBD                           TBD
```

## v0.8.0 — Controlled Sync

Yandex active collections are desired state; Local Library plus authoritative Coverage are actual state. Controlled Sync builds a read-only plan, previews safe downloads and blockers, validates staleness, requires explicit confirmation, rechecks each operation, and delegates acquisition to the production `DownloadService`.

Bulk acquisition remains `missing + wanted`. Unreviewed Missing, identity conflicts/not-analyzed state and unresolved Variant issues remain review work. `DIFFERENT_VERSION` never triggers automatic replacement. Local-only/outside-scope files are informational and are never deleted.

## v0.8.1 — Rich Yandex download metadata / provenance

The production Yandex download path writes available standard MP3 metadata and trusted MusicArk/Yandex provenance before atomic finalization. This keeps downloaded files useful after rescans and allows trusted provider identity recovery without weakening queue isolation or overwriting an existing user file on a filename collision.

## v0.8.2 — Local Metadata Editor / Yandex Metadata Import

v0.8.2 adds an explicit write boundary for existing user-owned MP3 files: structured/advanced ID3 editing, artwork and safe filename changes, Yandex search/Compare, selective Apply Metadata and explicit Apply + Bind. It also includes app-level ORIGINAL/CENSORED marks, reviewed-variant acceptance, Yandex artwork/playback and the narrow-window desktop safeguard.

Schema progression reaches `1.8.4` through forward-only migrations. Scan, Matching, Coverage and Sync remain non-mutating for existing user audio files; only an explicit Metadata Editor action may rewrite one.

## Next

The next version is intentionally **stabilization / TBD**. No v0.8.3 or v0.9 product slice is committed by this roadmap. New features should be defined only after the v0.8.2 mainline candidate is reviewed and its required verification gates are complete.
