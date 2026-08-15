# Changelog

All notable project changes are recorded here.

## Unreleased — v0.6.0 Missing Tracks / Library Coverage

### Added

- `LibraryCoverageService` and SQL-backed `CoverageRepository` over active Yandex memberships plus authoritative v0.5/v0.5.1/local state;
- primary coverage states `covered`, `missing`, `needs_review`, `not_analyzed` with a strict truth model;
- separate variant verification summary/filter for covered identities;
- global `(provider_id, external_id)` deduplication across Liked/playlists and playlist-scope order preservation;
- coverage scopes, search, sorting, pagination, row/details UI and Matching navigation;
- persistent user triage `wanted` / `ignored` / absence=`unreviewed`, including bulk actions;
- bridge commands `coverage_summary`, `coverage_tracks`, `coverage_track`, `coverage_collections`, `coverage_set_action`, `coverage_set_actions`;
- structured JSON environment payload for bulk provider IDs with `runInShell: false`;
- automatic schema `1.5.0 → 1.6.0` migration adding `provider_track_actions` only;
- Python coverage/migration/bridge regression tests and Flutter Coverage widget tests.

### Changed

- package/Flutter versions advanced to `0.6.0`;
- playlist duplicate occurrence storage keys are canonicalized back to payload provider identity before matching materialization;
- documentation now reflects the actual v0.5.1 contract: explicit single-track variant verification may use bounded exact-reference acquisition;
- v0.5.1 reference cache is explicitly documented as **not Local Library coverage**.

### Coverage policy

- only a current authoritative `UNMATCHED` result is `missing`;
- current accepted automatic/manual local identity is `covered`;
- current `CONFLICT`, stale manual accepted links, and invalid accepted links are `needs_review`;
- absent/stale automatic matching state is `not_analyzed`;
- `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED` never change accepted identity to Missing;
- a strict cached Yandex reference never establishes Covered by itself.

### Safety / performance

- coverage status is derived, not copied into a `missing_tracks` table;
- summary/list/filter/search/sort/pagination are SQL-backed;
- v0.6 adds no download/source-selection workflow;
- no local audio or Yandex mutation is introduced;
- migration preserves existing Yandex cache, Local Library, matching/manual/conflict state and variant results.

## v0.5.1 — Variant / Altered Track Detection

Added independent recording-version states (`SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, `NOT_CHECKED`), strict exact-ID reference resolution, optional ffmpeg decoded-audio comparison, bounded alignment/segment comparison, altered regions, independent variant fingerprints/cache, bridge/UI integration and schema 1.5.0.

Current-code clarification: an explicit single-track variant run may invoke bounded exact-reference acquisition when needed. That verification cache is not Local Library, does not create identity links, and is not a general download workflow.

## v0.5.0 — Identity Matching

Added bounded SQL candidate generation, transparent scoring, conservative `MATCHED / CONFLICT / UNMATCHED`, manual accept/reject precedence, fingerprints/invalidation, bridge/UI integration and schema 1.4.0.

## v0.4.0 — Local Library

Added read-only multi-root Local Library scanning/indexing, metadata extraction, incremental rescan, SQL search/sort/pagination and schema 1.3.0.

## v0.3.0 — Yandex Library / Playlists

Added cache-first Liked/playlists, ordered playlist membership including duplicates, lazy playlist content loading, Flutter navigation and schema 1.2.0.

## v0.2.0 — Persistent Library

Added credential-store token persistence, atomic Liked cache, cache-first startup/refresh and schema 1.1.x.

## v0.1.0 — Verified Yandex Likes MVP

Added focused Flutter sign-in/Liked UI, Python process bridge and real Yandex account/Liked-track flow.
