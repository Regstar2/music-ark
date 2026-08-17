# MusicArk Project Map

## Active desktop path — v0.8.2 integration baseline

```text
ui/musicark_ui/
  lib/main.dart                       top-level Yandex / Local / Matching / Missing / Downloads / Sync navigation
  lib/yandex_app.dart                 Yandex Library UI + covers + built-in playback + inline content marks
  lib/yandex_content_labels.dart      cached Yandex ORIGINAL/CENSORED mark management
  lib/audio_player.dart               application-wide media_kit player used by Local and Yandex playback
  lib/local_library_page.dart         Local Library UI + scan-on-activation + local content marks
  lib/metadata_editor_page.dart       explicit local metadata/artwork/filename editor
  lib/content_label_bridge.dart       app-level content mark subprocess bridge
  lib/variant_acceptance_bridge.dart  explicit reviewed-variant user decision bridge
  lib/matching_page.dart              Russian identity/variant comparison UI + labels + variant acceptance
  lib/coverage_page.dart              Coverage / Missing / wanted-ignored triage
  lib/download_page.dart              production user queue / local playback entry points
  lib/sync_page.dart                  Controlled Sync preview / blockers / confirmation / history
  lib/sync_bridge.dart                Sync subprocess bridge client

src/musicark/
  yandex_library.py                   cache-first Yandex orchestration + private playback preparation
  local_library/                      local scan / metadata / indexing
  metadata/                           explicit transactional MP3 metadata/artwork/filename writes
  content_labels/                     app-only ORIGINAL/CENSORED labels; no file/provider mutation
  matching/                           identity matching
  variant/                            recording/version verification + separate user acceptance
    acceptance.py                     accepts current reviewed variant without changing analyzer status
    acceptance_bridge.py              JSON subprocess boundary for that user decision
  coverage/                           authoritative derived coverage + user triage
  download/
    metadata.py                       v0.8.1 Yandex metadata/provenance enrichment for new downloads
    provider.py                       authorized Yandex acquisition reused by private playback cache
    service.py                        production download application boundary
    bridge.py                         Downloads JSON process boundary
  sync/
    models.py                         legacy-compatible + Controlled Sync plan/operation models
    planner.py                        read-only planner/fingerprint
    service.py                        staleness + confirmation + revalidation + enqueue-only Apply
    bridge.py                         Sync JSON process boundary
    safe_execution.py                 legacy entry point delegating to SyncService
  storage/
    liked_cache.py                    Liked snapshot including public provider artwork URL
    playlist_cache.py                 playlist snapshots including public provider artwork URL
    sync_storage.py                   immutable plan snapshot/history + execution result persistence
    sync_migration.py                 schema 1.7.0 → 1.8.0
    metadata_migration.py             schema 1.8.0 → 1.8.1 rich download metadata/provenance support
    metadata_editor_migration.py      schema 1.8.1 → 1.8.2 artwork/editor cache
    content_label_migration.py        schema 1.8.2 → 1.8.3 app-level content labels
    variant_acceptance_migration.py   schema 1.8.3 → 1.8.4 reviewed-variant user decisions
    database.py                       forward migration bootstrap
```

## Authoritative boundaries

Controlled Sync does not implement another matcher, Coverage engine, downloader or Local indexer. It reads the current state from those layers and coordinates only safe operations. `DownloadService.enqueue()` remains the production acquisition boundary used by Sync Apply.

Yandex tab playback is a separate user-initiated preview path. It reuses the authorized Yandex download provider only to create/reuse a file under `.musicark/playback/yandex`; that file is not inserted into Local Library, Matching or Coverage. Flutter receives the local playback path, never the protected provider media URL or credentials.

The v0.8.2 Metadata Editor is a separate explicit-write boundary. Local Scan, Matching, Coverage, Sync, `[[content-labels]]` and `[[variant-acceptance]]` never rewrite user audio files. ORIGINAL/CENSORED marks never mutate Yandex provider data or alter Matching identity. Variant acceptance never changes the raw analyzer classification; it only resolves whether the currently analyzed local recording remains an actionable review blocker.

Legacy sync planner assumptions such as `filename == yandex_<id>` and upload/replace/metadata candidates are historical compatibility only and are not production truth.

## Documentation entry points

- `docs/versions/v0.8.2.md` — current Metadata Editor / Yandex Library / Matching contract;
- `docs/versions/v0.8.1.md` — rich Yandex download metadata/provenance baseline;
- `docs/architecture/metadata-editor.md` — explicit local write boundary;
- `docs/architecture/content-labels.md` — ORIGINAL/CENSORED app-level marks;
- `docs/architecture/variant-acceptance.md` — user acceptance of reviewed recording versions;
- `docs/versions/v0.8.0.md` — Controlled Sync contract;
- `docs/architecture/architecture.md` — active boundaries and storage model;
- `docs/product/roadmap.md` — product sequence / stabilization boundary;
- `docs/testing/manual-test-plan.md` — Windows v0.8.2 validation;
- `docs/release/release-checklist.md` — current integration/release gate.
