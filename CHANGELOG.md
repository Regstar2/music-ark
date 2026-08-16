# Changelog

All notable project changes are recorded here.

## Unreleased — v0.7.0 Download

### Added

- application-level `DownloadService` that owns Coverage eligibility, persisted queue state, provider execution, Local Library indexing, exact identity linking, and Coverage refresh;
- strict ordinary eligibility `coverage_status=missing AND user_action=wanted`, including a second eligibility check immediately before execution;
- persistent queue lifecycle with `queued`, `running`, `completed`, `failed`, `cancelled`, `skipped`, retry, task history, and crash recovery from stale `running` to retryable `failed/interrupted`;
- real byte progress from streaming HTTP responses, indeterminate progress when `Content-Length` is unavailable, and throttled SQLite progress persistence;
- cooperative running cancellation through persisted `cancel_requested`, with `.part` cleanup and no fake resume support;
- persistent download target rooted in Local Library, with per-task target snapshots and a managed `MusicArk` child folder;
- Windows-safe stable filenames containing the Yandex external ID;
- efficient `LocalFileIndexer.index_file()` reusing v0.4 `LocalMetadataReader` and `LocalLibraryStorageRepository.apply_scan(... allow_removals=False)` without a full root rescan;
- exact post-download identity persistence using existing `MatchMethod.EXACT_ID` and a current post-index Local Library fingerprint;
- dedicated `musicark.download.bridge` commands for summary/tasks/enqueue/bulk/run/retry/cancel/history/settings/target/recovery;
- Flutter **Загрузки** navigation/page with summary, filters, target selection, real/indeterminate progress, Retry, Cancel, bulk wanted enqueue, and completed-history cleanup;
- single-track **В загрузки** action on `missing + wanted` Coverage rows;
- schema `1.7.0` forward migration extending the existing `download_tasks` table and adding `download_settings`;
- v0.7 Python integration/security/migration/progress/cancellation tests and Flutter Downloads widget tests;
- Flutter analyze/test job in pull-request CI;
- `.gitignore` protection against accidental commits of common downloaded audio formats.

### Changed

- Python and Flutter versions advanced to `0.7.0`;
- the existing `YandexMusicDownloadProvider` now supports explicit secure token injection, real streaming progress, cooperative cancellation, atomic `.part` promotion, provider error categories, and path-safe filenames;
- production Download reads credentials from `SystemCredentialStore`; legacy environment/local-properties lookup remains only for compatibility with older tooling/reference flows;
- v0.6 is now the completed Coverage input layer and v0.8 Sync remains future work.

### Post-download quality gate

A task becomes `completed` only after all of the following succeed:

```text
atomic valid file
→ normal Local Library index with non-NULL library_root_id
→ exact provider/local accepted identity
→ Coverage refresh = covered
```

HTTP success alone is not completion. Exact acquisition identity does not run fuzzy candidate selection and does not fabricate `Variant = SAME`.

### Safety / scope

- reference cache `.musicark/downloads/yandex/` remains separate from the user Download Library;
- token/direct download URLs are not persisted in queue payloads, SQLite, filenames, UI, or audit details;
- no YouTube ripping, VK scraping, torrent search/download, pirate index, DRM circumvention, subscription/access bypass, or automatic third-party fallback is introduced;
- existing local music remains read-only; v0.7 only creates new downloaded files inside the selected managed destination;
- baseline queue execution is intentionally sequential (`max concurrency = 1`) for reliability.

## v0.6.0 — Missing Tracks / Library Coverage

### Added

- SQL-backed Coverage deriving `covered`, `missing`, `needs_review`, and `not_analyzed` from active Yandex membership plus authoritative matching state;
- independent identity coverage, Variant state, and persistent `wanted / ignored / unreviewed` triage;
- global provider-identity deduplication across Liked/playlists, scopes/order, search/sort/filter/pagination, details and matching navigation;
- schema `1.6.0` forward migration adding `provider_track_actions`;
- Flutter **Недостающие** section and Python/Flutter regression coverage.

### Policy

- only current authoritative `UNMATCHED` without an accepted local link is Missing;
- accepted automatic/manual identity is Covered;
- conflict/stale/invalid accepted state is Needs Review;
- absent/stale automatic state is Not Analyzed;
- Variant states never turn an accepted identity into Missing;
- strict reference cache never establishes Local Library coverage.

## v0.5.1 — Variant / Altered Track Detection

- added independent `SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED` recording/version analysis;
- semantic variant metadata, strict exact-reference resolution/acquisition, optional ffmpeg decoded-audio comparison, bounded alignment, segment evidence, altered regions, cache/fingerprints, bridge/UI, and schema `1.5.0`;
- identity confidence remains independent from Variant/audio evidence;
- technical failures never become `DIFFERENT_VERSION`, and unclear evidence prefers `UNCERTAIN` over false `SAME`.

## v0.5.0 — Identity Matching

- added bounded candidate generation, transparent scoring, ambiguity handling, automatic/manual match persistence, stale-link invalidation, fingerprints, matching bridge/UI, and schema `1.4.0`;
- automatic matching remains precision-first: false positive identity is worse than conflict/unmatched.

## v0.4.0 — Local Library

- added multiple Local Library roots, read-only recursive/incremental scan, structured metadata via mutagen, SQL search/sort/pagination, native Windows folder picker, Local Library UI, and schema `1.3.0`;
- removing a root removes index state only; existing user audio is not mutated.

## v0.3.0 — Yandex Library / Playlists

- added cache-first Yandex Liked/playlists metadata/content, ordered playlist membership, generic collection snapshots, stale playlist cleanup, bridge/UI, and schema `1.2.0`.

## v0.2.0 — Persistent Library

- added secure Yandex token persistence through OS keyring, persistent Liked cache, cache-first startup/refresh, and schema `1.1.x` migrations.

## v0.1.0 — Verified Yandex Likes MVP

- focused Flutter sign-in/Liked UI, Python bridge, real Yandex account/liked-track provider flow, tests, and Windows setup documentation;
- real Windows launch, token authentication, and Liked retrieval were manually confirmed on 2026-08-11.
