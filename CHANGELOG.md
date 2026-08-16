# Changelog

All notable project changes are recorded here.

## Unreleased — v0.8.0 Controlled Sync

### Added

- `SyncService` application boundary coordinating authoritative Coverage, Local/Matching fingerprint state, persisted Sync plans and the production v0.7 `DownloadService`;
- read-only SQL/batched Sync Planner for all / Liked / one active Yandex Playlist scope with provider-identity and duplicate-occurrence deduplication;
- production operations `ENQUEUE_DOWNLOAD`, `REVIEW_IDENTITY`, `REVIEW_VARIANT`, `USER_DECISION_REQUIRED`, and informational `LOCAL_ONLY`;
- immutable plan snapshots with planner version, scope, exact target, input fingerprint, summary, persisted operation state/results and plan history;
- staleness detection for active Yandex membership, Matching/Local state, triage, Variant review state and target changes, excluding playback state;
- explicit-confirmation enqueue-only Apply with per-operation execution-time revalidation and active task deduplication;
- safe legacy compatibility: historical enum values/rows remain readable while v0.8 refuses legacy upload/replace/metadata plans;
- schema `1.8.0` forward migration extending existing `sync_plans` / `sync_operations` in place;
- audit events for plan creation/staleness/cancel/apply and operation enqueue/skip;
- Flutter **Синхронизация** navigation/page with scope/target, Current/Projected coverage, grouped blockers/operations, stale/legacy banners, confirmation, history/cancel and Matching/Downloads navigation;
- Python integration/migration/safety tests and Flutter Controlled Sync widget/navigation tests;
- `docs/versions/v0.8.0.md` plus updated architecture, roadmap, manual plan and release checklist.

### Policy / safety

- only current `missing + wanted` is the default bulk acquisition input;
- `missing + unreviewed` requires a decision; ignored Missing is never automatically downloaded;
- identity conflicts/not-analyzed state and Variant issues remain review work;
- `DIFFERENT_VERSION` never triggers a replacement download;
- Sync Apply delegates to `DownloadService.enqueue()` and never drains the global Downloads queue;
- local delete/move/rename/tag edits and Yandex likes/playlists/upload/replacement remain out of scope and must stay zero.

## v0.7.0 — Download + Local Playback

- added production `DownloadService`, persistent user queue/target, secure authorized provider transfer, byte progress/cancel/recovery, exact Local indexing/link/Coverage rebase, Downloads UI and embedded Local Playback;
- direct single-track Missing download remains explicit user intent and does not require or rewrite triage;
- schema advanced to `1.7.0`.

## v0.6.0 — Missing Tracks / Library Coverage

- added SQL-backed `covered / missing / needs_review / not_analyzed` Coverage and independent `wanted / ignored / unreviewed` triage;
- schema advanced to `1.6.0`.

## v0.5.1 — Variant / Altered Track Detection

- added independent `SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED` recording/version analysis; schema `1.5.0`.

## v0.5.0 — Identity Matching

- added precision-first persisted identity matching, conflicts/manual decisions and fingerprints; schema `1.4.0`.

## v0.4.0 — Local Library

- added multiple roots, read-only incremental indexing and Local Library UI; schema `1.3.0`.

## v0.3.0 — Yandex Library / Playlists

- added cache-first Liked/playlists metadata/content and active collection snapshots; schema `1.2.0`.

## v0.2.0 — Persistent Library

- added secure credential persistence and persistent Liked cache; schema `1.1.x`.

## v0.1.0 — Verified Yandex Likes MVP

- added focused Flutter sign-in/Liked UI, Python bridge and initial Yandex provider/storage flow.
