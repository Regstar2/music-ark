# codex-v0.8-controlled-sync

Authoritative implementation contract: `docs/versions/v0.8.0.md`.

v0.8 is **Controlled Sync**, not the historical remote/local filename planner. Use active cached Yandex collection membership as desired state and existing `CoverageRepository` / Matching / Variant / Local Library as actual state.

Planner is read-only. Bulk acquisition is only `missing + wanted`. Persist immutable plans, stale fingerprints, blockers and audit state. Apply requires confirmation and execution-time revalidation, and delegates only to production v0.7 `DownloadService.enqueue()`; it must never call legacy `DownloadSystem`, drain unrelated queue work, delete/rename/edit local music, or mutate Yandex.

Preserve legacy enum/rows for reading, but refuse unsupported legacy dangerous plans. Use schema 1.8.0 forward migration extending existing sync tables.
