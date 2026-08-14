# MusicArk

[Русская версия](README.md)

**Current version: 0.4.0 — Local Library.**

MusicArk is a Windows desktop application that combines a Yandex Music library with the user's local music collection. v0.4 adds local folder indexing and persists extracted metadata in the same SQLite database.

## What works in v0.4

### Yandex Music

- secure Yandex Music OAuth token sign-in through the OS credential store;
- cache-first session restore;
- Liked tracks;
- playlists and playlist tracks;
- search, sorting, refresh, and offline cache.

### Local Library

- a separate Local Library section;
- native Windows folder picker;
- multiple source roots;
- recursive scanning for MP3/FLAC/M4A/MP4/AAC/OGG/Opus/WAV files recognized by the metadata stack;
- title, artists, album, album artist, duration, and technical metadata via `mutagen`;
- filename fallback when title tags are missing;
- incremental new / changed / unchanged / removed reconciliation;
- unchanged detection by normalized path + file size + mtime_ns without re-hashing the whole collection;
- SQLite search, sorting, and `limit`/`offset` for large libraries;
- metadata details and file path view;
- per-file errors do not abort a scan;
- directory symlinks/reparse points are not recursively followed.

> **MusicArk v0.4 never modifies or deletes local music files.** Removing a source folder from MusicArk only removes index records. v0.4 does not rename, move, edit tags, transcode, or delete audio files.

## Local Library flow

```text
Local Library
      ↓
Add Folder
      ↓
select C:\Music
      ↓
Scan
      ↓
metadata → SQLite
      ↓
browse / search / sort
```

Roots and the local index remain in `.musicark/musicark.db` between launches. A rescan reads metadata only for new or changed files and removes stale index rows only after a complete accessible traversal of the source root.

## v0.4 architecture

```text
Flutter desktop
   ├─ Yandex UI → musicark.mvp_bridge → YandexLibraryService → Yandex provider/cache
   └─ Local UI  → musicark.mvp_bridge → LocalLibraryService
                                      → LocalLibraryScanner
                                      → LocalMetadataReader
                                      → LocalLibraryStorageRepository
                                      → shared SQLite
```

Local Library is not modeled as a Yandex provider. Folder paths are passed through the child process environment instead of shell command concatenation. The scanner uses `Path`/`os.walk` and contains no destructive filesystem operations.

The v0.4 forward SQLite migration is `1.3.0`; existing Yandex collection snapshots are preserved.

## Windows development run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

Do not delete `.musicark/musicark.db`; `initialize_database()` applies migration `1.3.0` automatically. The saved Yandex token also does not need to be removed.

## Manual Windows validation

Use a disposable folder such as `C:\MusicArk-Test`: add it, scan, restart, then add/change/delete a test audio file and rescan. Finally verify Yandex Likes, playlists, and the persisted Yandex session still work.

## Roadmap

```text
v0.1 — Yandex Likes MVP
v0.2 — Persistent Library
v0.3 — Yandex Library / Playlists
v0.4 — Local Library
v0.5 — Matching
v0.6 — Missing Tracks
v0.7 — Download
v0.8 — Sync
```

Standalone packaging/installers remain secondary infrastructure work.

See `docs/versions/v0.4.0.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
