# MusicArk Project Map

## Active desktop path — v0.9.1 UI over v0.8.2 music baseline

```text
ui/musicark_ui/
  lib/main.dart                       app bootstrap / deterministic locale + persisted production settings
  lib/app_shell.dart                  single global sidebar, utility pages, page lifetime and Now Playing boundary
  lib/app_ui_tokens.dart              shared desktop spacing/density/radius/responsive constants
  lib/musicark_mark.dart              theme-aware vector MusicArk brand mark
  lib/account_session.dart            provider-independent Flutter account/session state + bridge observer
  lib/account_control.dart            global profile/sign-in/logout control
  lib/yandex_app.dart                 standalone Yandex entry point / workspace re-export
  lib/yandex_workspace.dart           Tracks / Playlists / explicitly liked Albums workspace and detail views
  lib/yandex_content_labels.dart      cached Yandex ORIGINAL/CENSORED mark management
  lib/audio_player.dart               application-wide responsive media_kit Now Playing UI/controller
  lib/local_library_page.dart         Local Library UI + scan-on-activation + local content marks
  lib/metadata_editor_page.dart       explicit local metadata/artwork/filename editor
  lib/matching_page.dart              identity/variant comparison UI + labels + variant acceptance
  lib/coverage_page.dart              Coverage / Missing / wanted-ignored triage
  lib/download_page.dart              production user queue / local playback entry points
  lib/sync_page.dart                  Controlled Sync preview / blockers / confirmation / history

src/musicark/
  yandex_library.py                   cache-first liked tracks / playlists / liked albums orchestration
  providers/yandex_music_provider.py  authenticated Yandex reads, including explicit liked albums and album details
  storage/liked_cache.py              liked-track cache
  storage/playlist_cache.py           playlist index/detail cache
  storage/album_cache.py              liked-album index + lazy album-detail cache in generic provider tables
  local_library/                      local scan / metadata / indexing
  metadata/                           explicit transactional MP3 metadata/artwork/filename writes
  content_labels/                     app-only ORIGINAL/CENSORED labels; no file/provider mutation
  matching/                           identity matching
  variant/                            recording/version verification + separate user acceptance
  coverage/                           authoritative derived coverage + user triage
  download/                           authorized acquisition, metadata enrichment and queue service
  sync/                               read-only planner, staleness checks and enqueue-only Apply
```

## Yandex collection boundaries

`YandexLibraryService.bootstrap()` is cache-first. It exposes cached liked tracks, playlist metadata and the explicit Yandex Music liked-album index. `library_refresh()` refreshes those indexes without eagerly fetching every playlist or album. Opening one playlist or album loads that collection lazily and caches its ordered tracks.

The Albums tab is **not** derived from album tags on tracks in `Мне нравится / Liked`. It represents albums explicitly liked by the authenticated Yandex Music account through the pinned provider client. MusicArk only reads and caches this information; v0.9.1 does not like/unlike albums or otherwise mutate Yandex Music.

The album cache reuses `provider_collection_snapshots` and `provider_collection_items`, so v0.9.1 keeps SQLite schema `1.8.4`.

## Authoritative safety boundaries

The v0.9.x shell observes existing Yandex `session` payloads; it does not create another credential store or authentication API. Theme/locale preferences remain UI-only.

Controlled Sync does not implement another matcher, Coverage engine, downloader or Local indexer. It reads current state from those layers and delegates acquisition to Downloads.

Yandex playback is a user-initiated preview path. It creates/reuses a private file under `.musicark/playback/yandex`; that file is not inserted into Local Library, Matching or Coverage. Flutter receives the local playback path, never protected provider media URLs or credentials.

Metadata Editor remains the explicit ordinary write boundary. Local Scan, Matching, Coverage, Sync, content labels and variant acceptance never rewrite user audio files. ORIGINAL/CENSORED marks never mutate Yandex provider data or alter Matching identity.

## Documentation entry points

- `docs/versions/v0.9.1.md` — current Draft milestone and verification gate;
- `docs/architecture/ui-design-system.md` — desktop presentation rules;
- `docs/architecture/app-shell-settings.md` — shell/account/preferences boundaries;
- `docs/architecture/metadata-editor.md` — explicit local write boundary;
- `docs/architecture/content-labels.md` — ORIGINAL/CENSORED app-level marks;
- `docs/architecture/variant-acceptance.md` — reviewed recording decisions;
- `docs/testing/manual-test-plan.md` — Windows validation;
- `docs/release/release-checklist.md` — current acceptance gate.
