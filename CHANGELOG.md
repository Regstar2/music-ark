# Changelog

All notable project changes are recorded here.

## Unreleased — v0.4.0 Local Library

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
- Python regression tests for empty/nested scans, extension filtering, missing tags, corrupted files, Unicode paths, duplicate/overlapping roots, incremental changes, deletions, idempotency, pagination, and migration preservation;
- Flutter widget coverage for Local Library navigation, empty state, folder add/remove, scan result, track display, search, and sorting.

### Changed

- Python package and Flutter app version advanced to `0.4.0`;
- SQLite schema advanced to `1.3.0` through a forward-only migration;
- the existing `local_audio_files` table is extended instead of creating a separate database;
- local file SHA-256 is no longer recomputed for every unchanged scan in the new v0.4 pipeline;
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
- Python and Flutter regression coverage for the v0.3 flow.

### Changed

- Python package and Flutter app version advanced to `0.3.0`;
- full library refresh updates account, Likes, and playlist metadata without eagerly fetching every playlist body.

## v0.2.0 — Persistent Library

### Added

- secure Yandex token persistence through Python `keyring` / Windows Credential Locker;
- `PersistentLibraryService` orchestration layer;
- atomic SQLite Liked snapshot cache with membership removal support;
- schema migration `1.1.0` and repair migration `1.1.1`;
- cache-first startup, automatic refresh, search, sorting, last-update metadata, and sync diff.

## v0.1.0 — Verified Yandex Likes MVP

### Added

- focused Flutter sign-in and Liked tracks UI;
- minimal Python process bridge;
- real Yandex account/liked-track provider flow;
- Python unit tests and Flutter widget test;
- reproducible Windows setup/run/test documentation.

### Validation

- real Windows launch, token authentication, and Liked track retrieval were manually confirmed on 2026-08-11.
