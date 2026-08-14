# Changelog

All notable project changes are recorded here.

## Unreleased — v0.2.0 Persistent Library

### Added

- secure Yandex token persistence through Python `keyring` / Windows Credential Locker;
- `PersistentLibraryService` orchestration layer;
- atomic SQLite Liked snapshot cache with membership removal support;
- schema migration `1.1.0` for `provider_collection_snapshots` and `provider_collection_items`;
- repair migration `1.1.1` for incompatible experimental cache tables left by older local work;
- cache-first startup and automatic refresh of a saved session;
- search across title, artist, and album;
- library sorting by Yandex order, title, or artist;
- last-update metadata and added/removed sync diff;
- tests for persistent credentials/cache service behavior, snapshot replacement, duplicate IDs, and stale-schema repair.

### Changed

- project/package/UI version advanced to `0.2.0`;
- `YandexMusicProvider` accepts an explicit token for secure-session flows while keeping legacy fallbacks;
- `musicark.mvp_bridge` now exposes `bootstrap`, `login`, `refresh`, `cached`, and `logout`;
- refresh failures preserve the last successful cached library;
- logout clears both stored credentials and cached Liked data;
- liked-cache persistence ignores blank/duplicate provider track IDs instead of failing the whole snapshot;
- SQLite cache errors include the underlying safe SQLite diagnostic message;
- README, architecture, roadmap, scope, test plan, and version docs updated for v0.2.

## v0.1.0 — Verified Yandex Likes MVP

### Added

- focused Flutter sign-in and Liked tracks UI;
- minimal Python process bridge;
- real Yandex account/liked-track provider flow;
- Python unit tests and Flutter widget test;
- fresh-process circular-import regression test;
- reproducible Windows setup/run/test/build documentation.

### Fixed

- provider-first circular import caused by eager `MusicArkApp` package export.

### Validation

- real Windows launch, token authentication, and Liked track retrieval were manually confirmed on 2026-08-11.
