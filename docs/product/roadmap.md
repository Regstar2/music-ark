# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                  complete
v0.2   — Persistent Library                complete
v0.3   — Yandex Library / Playlists        complete
v0.4   — Local Library                     complete
v0.5.0 — Identity Matching                 complete
v0.5.1 — Variant / Altered Track Detection complete
v0.6   — Missing Tracks / Coverage         complete
v0.7   — Download + Local Playback         complete
v0.8   — Controlled Sync                   current
next   — stabilization / TBD               TBD
```

## v0.8 — Controlled Sync

Yandex active collections are desired state; Local Library plus authoritative Coverage are actual state. v0.8 creates an immutable read-only Sync Plan, previews safe downloads and blockers, validates staleness, requires explicit confirmation, rechecks each operation, and delegates acquisition to the production v0.7 `DownloadService`.

Bulk acquisition remains strictly `missing + wanted`. Unreviewed Missing, identity conflicts/not-analyzed state, and Variant issues remain review work. `DIFFERENT_VERSION` never triggers replacement. Local-only/outside-scope files are informational and are never deleted.

Apply is enqueue-only in the baseline and never drains unrelated queued downloads. No local delete/move/rename/tag mutation or Yandex mutation exists in v0.8.

After v0.8, prefer stabilization/reliability work until a concrete new product need is defined.
