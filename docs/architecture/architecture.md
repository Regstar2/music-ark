# MusicArk Architecture — v0.4

## Product boundaries

MusicArk now has two independent library boundaries which share application storage but not provider logic:

```text
Flutter desktop
        ↓
musicark.mvp_bridge
   ├───────────────────────────────┐
   ↓                               ↓
YandexLibraryService        LocalLibraryService
   ↓                               ↓
YandexMusicProvider         LocalLibraryScanner
   ↓                               ↓
Yandex API/cache            LocalMetadataReader
                                   ↓
                           LocalLibraryStorageRepository
                                   ↓
                              shared SQLite
```

Local Library is deliberately **not** implemented as `YandexMusicProvider` or another remote provider. Common models may be reused in later matching work, but filesystem scanning remains a separate boundary.

## Local Library layers

### Flutter

`LocalLibraryPage` owns presentation only: roots, search/sort controls, scan state, results, metadata details. Native folder selection is hidden behind `LocalFolderPicker` so widget tests do not require a real Windows dialog.

### Process bridge

`musicark.mvp_bridge` exposes:

- `local_roots`;
- `local_root_add`;
- `local_root_remove`;
- `local_scan`;
- `local_tracks`;
- `local_track`;
- `local_stats`.

Root paths are supplied to the child process through `MUSICARK_LOCAL_ROOT` rather than command-line string concatenation. Track listing exposes `limit`, `offset`, `search`, `sort`, and optional root filtering.

### LocalLibraryService

Coordinates roots, scanning, storage queries, and shared DB initialization. It does not contain filesystem traversal or metadata parsing details.

### LocalLibraryScanner

- recursive `os.walk`;
- supported-extension filtering;
- no directory symlink/reparse traversal;
- one-file errors are isolated;
- current filesystem state is compared against DB state by normalized path;
- unchanged means file size and `mtime_ns` are unchanged;
- metadata is read only for new/changed files;
- missing rows are deleted only after a complete traversal; if the walker reports an access error, deletion reconciliation is suppressed for that scan.

### LocalMetadataReader

Read-only `mutagen` adapter. It extracts matching-relevant tags and technical fields. Missing title falls back to filename stem; missing artist remains empty at storage level and is rendered as `Unknown Artist` in UI.

### LocalLibraryStorageRepository

Uses the existing MusicArk SQLite database. Scan writes use a single transaction with `executemany` and a temporary `seen` table rather than per-file commits or O(n²) comparisons.

## SQLite v1.3.0

`local_library_roots` stores persistent source folders. Existing `local_audio_files` is extended with root identity, normalized path, timestamps, structured metadata, technical fields, availability, and last-seen data. `normalized_path` has a unique index.

Legacy local rows are preserved as `availability='legacy'` instead of being treated as current v0.4 source-root records. Yandex `provider_collection_*` tables are not dropped or cleared by the migration.

## Windows path policy

Comparison keys use a resolved path, normalized separators, trailing-separator removal, and `casefold()` to model case-insensitive Windows identity. Duplicate and parent/child overlapping roots are rejected for a predictable one-file/one-index-row rule.

## Safety boundary

The v0.4 supported path contains no audio-file write API. It never renames, moves, deletes, edits tags, transcodes, or changes artwork. Removing a root deletes only MusicArk index records.

## Preparation for v0.5

Structured local fields include `title`, `artists`, `album`, `duration`, and `path`, which can later be compared with Yandex track snapshots without coupling the two storage domains in v0.4.
