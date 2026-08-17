# MusicArk Project Map

## Active desktop path — v0.8

```text
ui/musicark_ui/
  lib/main.dart                    top-level Yandex / Local / Matching / Missing / Downloads / Sync navigation
  lib/yandex_app.dart              Yandex Library UI
  lib/yandex_content_labels.dart   cached Yandex ORIGINAL/CENSORED mark management
  lib/local_library_page.dart      Local Library UI + scan-on-activation + local content marks
  lib/metadata_editor_page.dart    explicit local metadata/artwork/filename editor
  lib/content_label_bridge.dart    app-level content mark subprocess bridge
  lib/matching_page.dart           identity + Variant review UI
  lib/coverage_page.dart           Coverage / Missing / wanted-ignored triage
  lib/download_page.dart           v0.7 production user queue / local playback entry points
  lib/sync_page.dart               v0.8 plan preview / blockers / confirmation / history
  lib/sync_bridge.dart             v0.8 subprocess bridge client

src/musicark/
  yandex_library.py                cache-first Yandex orchestration
  local_library/                   local scan / metadata / indexing
  metadata/                        explicit transactional MP3 metadata/artwork/filename writes
  content_labels/                  app-only ORIGINAL/CENSORED labels; no file/provider mutation
  matching/                        identity matching
  variant/                         recording/version verification
  coverage/                        authoritative derived coverage + user triage
  download/
    service.py                     v0.7 production download application boundary
    bridge.py                      Downloads JSON process boundary
  sync/
    models.py                      legacy-compatible + v0.8 plan/operation models
    planner.py                     read-only Controlled Sync planner/fingerprint
    service.py                     staleness + confirmation + revalidation + enqueue-only Apply
    bridge.py                      Sync JSON process boundary
    safe_execution.py              legacy entry point delegating to SyncService
  storage/
    sync_storage.py                immutable plan snapshot/history + execution result persistence
    sync_migration.py              schema 1.7.0 → 1.8.0
    metadata_editor_migration.py   schema 1.8.1 → 1.8.2 artwork/editor cache
    content_label_migration.py     schema 1.8.2 → 1.8.3 app-level content labels
    database.py                    forward migration bootstrap
```

## Authoritative boundaries

v0.8 **does not** implement another matcher, Coverage engine, downloader or Local indexer. It reads the current state from those layers and coordinates only safe operations. `DownloadService.enqueue()` remains the only production acquisition boundary used by Sync Apply.

The v0.8.2 Metadata Editor is a separate explicit-write boundary. Local Scan, Matching, Coverage, Sync and `[[content-labels]]` never rewrite user audio files. ORIGINAL/CENSORED marks also never mutate Yandex provider data or alter Matching/Coverage semantics.

Legacy sync planner assumptions such as `filename == yandex_<id>` and upload/replace/metadata candidates are historical compatibility only and are not production truth.

## Documentation entry points

- `docs/versions/v0.8.2.md` — current Metadata Editor / content-label follow-up contract;
- `docs/architecture/metadata-editor.md` — explicit local write boundary;
- `docs/architecture/content-labels.md` — ORIGINAL/CENSORED app-level marks;
- `docs/versions/v0.8.0.md` — Controlled Sync contract;
- `docs/architecture/architecture.md` — active boundaries and storage model;
- `docs/product/roadmap.md` — product sequence / stabilization boundary;
- `docs/testing/manual-test-plan.md` — Windows controlled dataset validation;
- `docs/release/release-checklist.md` — release gate.
