# MusicArk Project Map

## Active desktop path — v0.8

```text
ui/musicark_ui/
  lib/main.dart                 top-level Yandex / Local / Matching / Missing / Downloads / Sync navigation
  lib/yandex_app.dart           Yandex Library UI
  lib/local_library_page.dart   Local Library UI
  lib/matching_page.dart        identity + Variant review UI
  lib/coverage_page.dart        Coverage / Missing / wanted-ignored triage
  lib/download_page.dart        v0.7 production user queue / local playback entry points
  lib/sync_page.dart            v0.8 plan preview / blockers / confirmation / history
  lib/sync_bridge.dart          v0.8 subprocess bridge client

src/musicark/
  yandex_library.py             cache-first Yandex orchestration
  local_library/                local scan / metadata / indexing
  matching/                     identity matching
  variant/                      recording/version verification
  coverage/                     authoritative derived coverage + user triage
  download/
    service.py                  v0.7 production download application boundary
    bridge.py                   Downloads JSON process boundary
  sync/
    models.py                   legacy-compatible + v0.8 plan/operation models
    planner.py                  read-only Controlled Sync planner/fingerprint
    service.py                  staleness + confirmation + revalidation + enqueue-only Apply
    bridge.py                   Sync JSON process boundary
    safe_execution.py           legacy entry point delegating to SyncService
  storage/
    sync_storage.py             immutable plan snapshot/history + execution result persistence
    sync_migration.py           schema 1.7.0 → 1.8.0
    database.py                 forward migration bootstrap
```

## Authoritative boundaries

v0.8 **does not** implement another matcher, Coverage engine, downloader or Local indexer. It reads the current state from those layers and coordinates only safe operations. `DownloadService.enqueue()` remains the only production acquisition boundary used by Sync Apply.

Legacy sync planner assumptions such as `filename == yandex_<id>` and upload/replace/metadata candidates are historical compatibility only and are not production truth.

## Documentation entry points

- `docs/versions/v0.8.0.md` — Controlled Sync contract;
- `docs/architecture/architecture.md` — active boundaries and storage model;
- `docs/product/roadmap.md` — product sequence / stabilization boundary;
- `docs/testing/manual-test-plan.md` — Windows controlled dataset validation;
- `docs/release/release-checklist.md` — release gate.
