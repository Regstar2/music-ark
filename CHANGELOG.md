# Changelog

All notable project changes are recorded here.

## Unreleased — v0.6.0 Missing Tracks / Library Coverage

### Added

- SQL-backed `LibraryCoverageService` / `CoverageRepository` deriving `covered`, `missing`, `needs_review`, and `not_analyzed` from active Yandex membership plus authoritative v0.5 state;
- strict separation of identity coverage, v0.5.1 variant state, and persistent user triage;
- global `(provider_id, external_id)` deduplication across Liked/playlists, playlist scopes/order, memberships, search/sort/filter/pagination, and Coverage details/navigation;
- persistent `wanted` / `ignored` decisions (`no row = unreviewed`) and bulk triage;
- bridge commands `coverage_summary`, `coverage_tracks`, `coverage_track`, `coverage_collections`, `coverage_set_action`, `coverage_set_actions`, with structured JSON bulk payload and no shell interpolation;
- schema `1.6.0` forward migration adding only `provider_track_actions` plus its lookup index;
- Flutter **Недостающие** section, default Missing filter, coverage/analysis summary, secondary variant warnings, triage, bulk actions, and empty states;
- Python coverage/migration/bridge regression tests and Flutter widget tests.

### Coverage policy

- only a current authoritative `UNMATCHED` without an accepted current local link is `missing`;
- a current accepted automatic/manual local identity is `covered`;
- `CONFLICT`, stale manual decisions, and invalid accepted links are `needs_review`;
- absent/stale automatic matching state is `not_analyzed`;
- `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED` remain secondary and never turn an accepted identity into Missing;
- v0.5.1 strict reference cache is never Local Library coverage and never establishes Covered by itself.

### Changed

- Python/Flutter versions advanced to `0.6.0`;
- provider identity materialization now canonicalizes playlist duplicate storage keys back to payload `external_id`;
- documentation now matches the tested v0.5.1 contract: an explicit single-track verification may use bounded exact-reference acquisition, without becoming a general download workflow.

### Safety / performance

- no `missing_tracks` copy table: technical coverage remains derived;
- summary/list/filter/search/sort/pagination are SQL-backed and avoid N+1 provider-track queries;
- v0.6 adds no download/source-selection execution, filesystem mutation, or Yandex mutation;
- forward migration preserves Yandex cache, Local Library, matching/manual/conflict state, and variant results.

## v0.5.1 — Variant / Altered Track Detection

### Added

- independent variant states `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED` above unchanged v0.5 identity state;
- `MetadataVariantDetector` with semantic markers for live/remix/mix/acoustic/instrumental/remaster/radio edit/edit/extended/demo/clean/explicit/censored/uncensored variants;
- provider explicit/content-warning evidence kept separate from censorship conclusions;
- strict `ReferenceAudioResolver` for exact `yandex_<id>.<ext>` / `yandex-<id>.<ext>` reference files;
- `AudioDecoder` abstraction and optional `FfmpegAudioDecoder` using mono signed-16 PCM at 11025 Hz through a pipe;
- bounded energy-envelope alignment for small encoder/leading-silence offsets;
- segment-level comparison with policy-controlled windows/hop, energy/spectral/waveform evidence, and merged altered regions;
- conservative `VariantClassifier` with separate duration, metadata, global/median similarity, low-window ratio, region count/length signals;
- evidence-based `possible_clean_or_censored_variant` reason for localized divergence under strong recording/explicit evidence;
- `track_variant_results` persistence with provider/local/reference fingerprints and analyzer version;
- independent cache invalidation when provider variant metadata, local file, reference file, or analyzer version changes;
- bridge commands `variant_capabilities`, `variant_summary`, `variant_run`, `variant_run_all_available`, `variant_result`, and `variant_results`;
- Matching-page secondary variant badges, separate variant detail section, altered-region display, single-track verification, batch verification, decoder-unavailable and progress/error states;
- synthetic Python tests for audio comparison, metadata variants, strict references, graceful failures, cache/invalidation, and v1.4→v1.5 migration preservation;
- Flutter widget tests for SAME/ALTERED/DIFFERENT VERSION/NOT CHECKED, verification controls, altered regions, unavailable decoder, progress, error, and result refresh.

### Changed

- package and Flutter versions advanced to `0.5.1`;
- SQLite schema advanced from `1.4.0` to `1.5.0` through a forward-only migration;
- v0.5 matching is documented explicitly as **identity matching**, while v0.5.1 is a second recording/version-verification layer;
- decoded PCM remains compact/in-memory and is never stored as SQLite blobs or persistent temporary WAV files;
- Matching UI keeps identity confidence separate from audio/variant evidence.

### Variant policy

- false-positive `SAME` is considered worse than `UNCERTAIN`;
- semantic Live/Remix/Acoustic/Instrumental/Radio Edit mismatches cannot become `SAME` solely because title/artist identity is close;
- technical decoder/alignment/file failures never become `DIFFERENT_VERSION`;
- explicit metadata alone never proves clean/censored status;
- deep audio comparison requires an exact provider reference; an explicit single-track run may acquire one exact reference on demand, while batch verification remains bounded to already-available references;
- audio verification begins only after a v0.5 `MATCHED` or manually accepted identity.

### Safety / performance

- no external matching, metadata, fingerprint, or ML service is introduced;
- ffmpeg is optional and its absence does not break Yandex, Local Library, or identity matching;
- no local music file is renamed, moved, deleted, edited, or transcoded by variant analysis;
- no PCM crosses Flutter ↔ Python;
- unchanged successful pairs skip redundant decode;
- batch work is bounded to matched/reference-available pairs and isolates per-file failures;
- existing Yandex cache, Local Library, v0.5 matches, `track_links`, conflicts, and manual decisions are preserved by migration.

## v0.5.0 — Matching

### Added

- offline `MatchingService` orchestration with separate candidate-generation, scoring, decision, persistence, and input/index boundaries;
- unique provider-track materialization from Liked + playlist cache membership by `(provider_id, external_id)`;
- bounded SQL candidate generation using normalized title, normalized artist-set text, and duration buckets;
- transparent score breakdown for title, artists, duration, album, filename fallback, exact-id signal, and final confidence;
- conservative `matched` / `conflict` / `unmatched` decision policy with best-vs-second ambiguity margin;
- multiple persisted conflict candidates, manual accept, persistent reject, and manual-decision precedence;
- matcher version and provider/local fingerprints for incremental reruns;
- stale local-link invalidation when a linked indexed file disappears;
- bridge commands `matching_summary`, `matching_run`, `matching_results`, `matching_result`, `matching_accept`, and `matching_reject`;
- Flutter Matching page with summary, filters, search, sorting, pagination, conflict details, accept, and reject;
- Python normalization/scoring/ambiguity/persistence/scale/migration/identity tests and Flutter widget coverage.

### Changed

- package and Flutter versions advanced to `0.5.0`;
- SQLite schema advanced from `1.3.0` to `1.4.0` through a forward-only migration;
- legacy `MatchingEngine` is now a compatibility facade over the v0.5 pipeline rather than the production algorithm;
- legacy canonical `tracks`, `track_links`, and `match_conflicts` are reused/extended instead of creating a parallel canonical model;
- exact Yandex-ID matching recognizes only the strict filename convention instead of arbitrary numeric path substrings.

### Matching policy

- automatic match: confidence `>= 0.90` and best-vs-second margin `>= 0.04`;
- conflict: confidence `>= 0.70` when auto-match policy is not satisfied;
- unmatched: confidence `< 0.70` or no candidates;
- weights: title `0.50`, artists `0.30`, duration `0.15`, album `0.05`;
- semantic variants such as live/remix/acoustic/instrumental are preserved and guarded against unsafe auto-collapse;
- precision of automatic matches is prioritized over recall.

### Safety

- no network dependency is introduced for matching;
- no local audio file is renamed, moved, deleted, or edited;
- no Yandex library mutation is performed;
- v0.4 Yandex cache, Local Library data, and credentials are preserved by migration.

## v0.4.0 — Local Library

### Added

- `LocalLibraryService` application boundary independent from Yandex providers;
- `LocalLibraryScanner` with recursive, non-symlink traversal and per-file error isolation;
- read-only `LocalMetadataReader` based on `mutagen`;
- persistent `local_library_roots` configuration;
- incremental file reconciliation using normalized path + size + `mtime_ns`;
- batch/transactional local index persistence and deletion reconciliation;
- local library bridge commands for roots, scans, tracks, track details, and stats;
- `limit`/`offset`, SQL search, sorting, and root-aware storage API;
- native Windows directory picker via Flutter `file_selector`;
- Local Library desktop page with roots, scan state, results, track list, search, sorting, and details;
- Python regression tests for empty/nested scans, extension filtering, missing tags, corrupted files, Unicode paths, duplicate/overlapping roots, incremental changes, deletions, idempotency, pagination, unavailable roots, and migration preservation;
- Flutter widget coverage for Local Library navigation, empty state, folder add/remove, scan result, track display, search, and sorting.

### Changed

- Python package and Flutter app version advanced to `0.4.0`;
- SQLite schema advanced to `1.3.0` through a forward-only migration;
- the existing `local_audio_files` table is extended instead of creating a separate database;
- the v0.4 scanner avoids recalculating SHA-256 for unchanged files;
- legacy Local Library storage methods remain for compatibility, while the supported v0.4 UI uses the new service/scanner boundary.

### Safety

- Local Library is read-only in v0.4: no rename, move, tag editing, deletion, transcoding, or artwork mutation;
- removing a source root removes only MusicArk index records;
- Yandex collection cache and stored credentials are not deleted by the local-library migration;
- directory symlinks/reparse points are not recursively followed.

## v0.3.0 — Yandex Library / Playlists

### Added

- `YandexLibraryService` orchestration above provider + credentials + collection caches;
- lazy Yandex playlist metadata and single-playlist content APIs;
- `PlaylistCacheRepository` using generic `provider_collection_snapshots/items`;
- ordered playlist membership snapshots with duplicate occurrence support;
- migration `1.2.0` adding generic collection metadata while preserving v0.2 Liked rows;
- stale playlist removal after full library refresh;
- bridge commands `liked_refresh`, `playlists`, `playlist`, `playlist_refresh`, `library_refresh`;
- desktop sidebar navigation for Liked, playlists, and individual playlists;
- playlist search and Yandex/title sorting; track search and Yandex/title/artist sorting;
- cached playlist opening with background network refresh and non-destructive error states;
- Python regression tests for playlist cache, migration, bridge, provider lazy loading, deletion, duplicates, empty playlists, and offline behavior;
- Flutter widget coverage for cached startup, sidebar, playlist navigation, search, sorting, refresh, logout, and network-error fallback.

### Changed

- Python package and Flutter app version advanced to `0.3.0`;
- full library refresh updates account, Likes, and playlist metadata but intentionally does not fetch every playlist body;
- old `refresh`/`cached` bridge behavior and legacy eager provider scan remain compatible;
- documentation and roadmap updated for the v0.3 product boundary.

### Fixed

- updated the legacy platform-bridge schema regression to expect schema `1.2.0` after the v0.3 migration;
- prevented Flutter sorting dropdown overflow in desktop/widget layouts;
- removed the analyzer warnings reported by the Windows v0.3 validation run.

## v0.2.0 — Persistent Library

### Added

- secure Yandex token persistence through Python `keyring` / Windows Credential Locker;
- `PersistentLibraryService` orchestration layer;
- atomic SQLite Liked snapshot cache with membership removal support;
- schema migration `1.1.0` and repair migration `1.1.1`;
- cache-first startup, automatic refresh, search, sorting, last-update metadata, and sync diff.

### Changed

- `musicark.mvp_bridge` added `bootstrap`, `login`, `refresh`, `cached`, and `logout`;
- refresh failures preserve the last successful cached library;
- logout clears stored credentials and cached Liked data.

## v0.1.0 — Verified Yandex Likes MVP

### Added

- focused Flutter sign-in and Liked tracks UI;
- minimal Python process bridge;
- real Yandex account/liked-track provider flow;
- Python unit tests and Flutter widget test;
- reproducible Windows setup/run/test documentation.

### Validation

- real Windows launch, token authentication, and Liked track retrieval were manually confirmed on 2026-08-11.
