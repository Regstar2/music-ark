# Changelog

All notable project changes are recorded here. Entries describe the current code history and do not imply a published GitHub Release unless a release/tag exists separately.

## Unreleased — v0.8.2 mainline candidate

### v0.8.2 — Local Metadata Editor & Yandex Metadata Import

#### Added

- explicit Metadata Editor for existing local MP3/ID3 files with structured fields, Advanced Tags, artwork replacement/removal and safe filename editing;
- preservation of unknown/custom ID3 frames unless explicitly changed;
- transactional same-directory copy → write → MPEG/read-back validation → atomic replace pipeline;
- single-file reindex, SHA-256 refresh and targeted Matching refresh after a successful metadata write;
- backend-only Yandex Track search with separate title/artist inputs, Compare and selective metadata/artwork import;
- **Apply Metadata** without automatic user-confirmed Exact identity;
- **Apply + Bind** with `exact_id`, confidence `1.0`, reason `user_confirmed` and trusted embedded provenance;
- app-level ORIGINAL/CENSORED labels for local tracks and cached Yandex identities, including Matching detail controls;
- separate reviewed-variant acceptance for `ALTERED`, `DIFFERENT_VERSION` and `UNCERTAIN`, bound to current analysis evidence and reversible without rewriting analyzer status;
- Yandex Library artwork, built-in playback and playlist playback through a private backend-prepared cache;
- narrow-window Yandex workspace safeguard using an approximately 920 px minimum workspace plus horizontal scrolling;
- schema migrations `1.8.2 → 1.8.3` for content labels and `1.8.3 → 1.8.4` for variant acceptance;
- Python and Flutter regression coverage for metadata editing, content labels, variant acceptance, Yandex controls/playback and narrow layout.

#### Safety / boundaries

- Scan, Matching, Coverage and Controlled Sync remain read-only for existing user audio files;
- explicit Metadata Editor actions are the normal application path allowed to modify an existing indexed audio file;
- content labels do not mutate Yandex, audio tags, identity or confidence;
- variant acceptance does not rewrite `track_variant_results.status` to `SAME` and becomes invalid when its analysis evidence changes;
- Yandex playback keeps credentials and protected/signed provider media URLs out of Flutter;
- playback-cache files are not inserted into Local Library, Matching or Coverage;
- writable metadata format remains MP3/ID3 only in this baseline.

#### Verification state

- PR #13 recorded earlier partial Windows checks, stale Flutter harness failures and analyzer findings before later stabilization commits;
- those historical results are not treated as verification of the current integration branch;
- current integration-branch Python/Flutter/Windows checks must be recorded separately when actually run.

### v0.8.1 — Rich Yandex download metadata / provenance

- Yandex downloads write available standard metadata and trusted MusicArk/Yandex provenance into newly acquired MP3 files;
- download materialization keeps the `.part → validate → metadata → atomic final` sequence;
- artwork enrichment is best-effort and does not weaken critical file validation;
- an existing user file is not overwritten merely because its filename collides with the proposed download name;
- Downloads gained the Wanted view/select-all flow while queue isolation remained intact;
- schema advanced from `1.8.0` to `1.8.1`.

## v0.8.0 — Controlled Sync

### Added

- `SyncService` application boundary coordinating authoritative Coverage, Local/Matching fingerprint state, persisted Sync plans and the production v0.7 `DownloadService`;
- read-only SQL/batched Sync Planner for all / Liked / one active Yandex Playlist scope with provider-identity and duplicate-occurrence deduplication;
- operations `ENQUEUE_DOWNLOAD`, `REVIEW_IDENTITY`, `REVIEW_VARIANT`, `USER_DECISION_REQUIRED`, and informational `LOCAL_ONLY`;
- immutable plan snapshots with planner version, scope, exact target, input fingerprint, summary, persisted operation state/results and plan history;
- staleness detection for active Yandex membership, Matching/Local state, triage, Variant review state and target changes, excluding playback state;
- explicit-confirmation enqueue-only Apply with per-operation execution-time revalidation and active task deduplication;
- schema `1.8.0` forward migration extending existing sync tables in place;
- Flutter Sync navigation/page and Python/Flutter regression coverage.

### Policy / safety

- only current `missing + wanted` is the default bulk acquisition input;
- `missing + unreviewed` requires a decision; ignored Missing is never automatically downloaded;
- identity conflicts/not-analyzed state and unresolved Variant issues remain review work;
- `DIFFERENT_VERSION` never triggers automatic replacement;
- Sync Apply delegates to `DownloadService.enqueue()` and never drains the global Downloads queue;
- local delete/move/rename/tag edits and Yandex likes/playlists/upload/replacement remain out of scope.

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
