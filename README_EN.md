# MusicArk

[Русская версия](README.md)

**Current version: 0.3.0 — Yandex Library / Playlists.**

MusicArk is a desktop-first application for preserving and later synchronizing a personal music library. In v0.3 the active provider is Yandex Music.

## What works in v0.3

- one-time Yandex Music OAuth token sign-in with the token saved in the OS credential store;
- cache-first startup without entering the token again;
- Liked tracks with refresh, offline fallback, search, and sorting;
- the user's Yandex Music playlist list;
- opening a playlist and viewing tracks in the original Yandex order;
- local SQLite snapshots for playlist metadata, membership, and track position;
- lazy playlist-content refresh when a playlist is opened;
- Refresh Library for account + Likes + playlist metadata without an eager N-playlist scan;
- stale playlist cache removal after a confirmed full library refresh;
- offline access to playlist snapshots that were loaded successfully before;
- logout clears both credentials and provider cache.

## v0.3 architecture

```text
Flutter desktop UI
        ↓
musicark.mvp_bridge
        ↓
YandexLibraryService
   ↓             ↓
Yandex provider  SQLite collection cache
        ↓
   yandex-music
```

Flutter does not depend on `yandex-music` or SQLite details. Third-party API objects remain inside the provider boundary.

SQLite uses generic provider collections:

- `yandex_music / liked`;
- `yandex_music / playlist:<external_id>`.

The token is not stored in SQLite and is not passed through argv. On login the UI passes it to the child bridge process only through the environment, after which the OS credential store is used.

## Windows development run

From the repository root:

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

Do not delete an existing `.musicark/musicark.db`: `initialize_database()` applies the forward-only `1.2.0` migration automatically.

## Real Yandex validation

Unit/widget tests do not require a real account. Before closing v0.3, manually validate on Windows: the saved session, real playlists, playlist tracks, refresh, restart/offline cache behavior, and logout. Never commit an OAuth token.

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

Standalone packaging/installers are not a priority at this stage.

See `docs/versions/v0.3.0.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
