# MusicArk Project Map

## Active desktop path — v0.9.7 utility UI over v0.8.2 music baseline

```text
ui/musicark_ui/
  lib/main.dart                       app bootstrap / deterministic locale + persisted production settings
  lib/app_shell.dart                  single global sidebar, utility pages, page lifetime and Now Playing boundary
  lib/app_ui_tokens.dart              shared desktop spacing/density/radius/responsive constants
  lib/musicark_mark.dart              theme-aware vector MusicArk brand mark
  lib/account_session.dart            provider-independent Flutter account/session state + bridge observer
  lib/account_control.dart            global profile/sign-in/logout control
  lib/settings_page.dart              responsive appearance/language/provider utility settings
  lib/help_page.dart                  grouped offline RU/EN workflow help and Settings return path
  lib/about_page.dart                 version/environment/diagnostics/licenses/project utility page
  lib/yandex_app.dart                 standalone Yandex entry point / workspace re-export
  lib/yandex_workspace.dart           Tracks / Playlists / explicitly liked Albums workspace and detail views
  lib/yandex_content_labels.dart      cached Yandex ORIGINAL/CENSORED mark management
  lib/audio_player.dart               application-wide responsive media_kit Now Playing UI/controller
  lib/local_library_page.dart         Local Library desktop UI + multi-root view filter + scan/content marks
  lib/metadata_editor_page.dart       explicit local metadata/artwork/filename editor
  lib/matching_page.dart              responsive Yandex↔Local comparison workspace + detail/manual decisions
  lib/coverage_page.dart              Coverage / Missing / wanted-ignored triage
  lib/download_page.dart              production queue / safe task removal / bulk actions / local playback
  lib/sync_page.dart                  responsive Controlled Sync status / coverage / filtered operation plan
  lib/sync_localizations_ext.dart     Sync presentation adapter over the existing generated RU/EN catalog

src/musicark/
  mvp_bridge.py                       desktop process boundary, including typed Local root-ID filters
  local_library/                      local scan / metadata / indexing / multi-root query orchestration
  storage/local_library_storage.py    SQLite Local roots/tracks and parameterized multi-root filtering
  yandex_library.py                   cache-first liked tracks / playlists / liked albums orchestration
  providers/yandex_music_provider.py  authenticated Yandex reads, including explicit liked albums and album details
  storage/liked_cache.py              liked-track cache
  storage/playlist_cache.py           playlist index/detail cache
  storage/album_cache.py              liked-album index + lazy album-detail cache in generic provider tables
  metadata/                           explicit transactional MP3 metadata/artwork/filename writes
  content_labels/                     app-only ORIGINAL/CENSORED labels; no file/provider mutation
  matching/                           identity matching
  variant/                            recording/version verification + separate user acceptance
  coverage/                           authoritative derived coverage + user triage
  download/                           authorized acquisition, metadata enrichment and queue service
  sync/                               read-only planner, staleness checks and enqueue-only Apply
```

## Utility presentation boundary

v0.9.7 changes only the Flutter presentation of Settings, Help and About. These pages remain inside the existing shell `IndexedStack` and keep the application-wide Now Playing boundary intact.

```text
Settings
  → AppSettingsController
  → existing typed UI preference store

provider account card
  → AccountSessionController
  → existing Yandex session payload observer

Help
  → local generated RU/EN ARB resources
  → no web request / no music-domain mutation

About diagnostics
  → AppInfo + OS + current UI preferences
  → clipboard without credentials/library contents
```

Utility content is constrained to about `1180 px` on large desktops and reflows through `LayoutBuilder` on smaller windows. Help/About return to Settings through the existing shell index selection; no routing or state-management framework is introduced. The existing `MusicArkMark` is reused in About instead of adding a brand asset pipeline.

The GitHub project action uses a copy-link fallback because v0.9.7 does not add a new external-URL dependency solely for one utility action.

## Sync presentation boundary

v0.9.6 changes only Flutter presentation around the existing Controlled Sync bridge. Scope/folder changes still create a fresh plan through the existing application boundary; Apply still rebuilds/revalidates the current diff and requires explicit confirmation.

```text
SyncPage
  → scopes / target / current
  → createPlan(scope)
  → summary + operations

local plan filter
  → filters already returned operations only
  → no bridge call / no persisted state change

explicit user decision
  → setAction(externalId, wanted|ignored)
  → createPlan(scope)

confirmed Sync
  → createPlan(scope)
  → confirmation dialog
  → apply(planId, confirm: true)
  → existing DownloadService enqueue boundary
```

The v0.9.6 plan filters are presentation state only. They do not create a second planner, change Coverage/Matching/Variant truth or add filesystem/provider mutations. Missing artwork in Sync operations uses a local placeholder rather than extending the backend contract for decoration.

## Matching presentation boundary

v0.9.3 changes only the Flutter presentation of existing Matching/Variant results. The bridge remains authoritative for filtering, sorting, identity decisions and Variant analysis.

```text
MatchingPage
  → matchingSummary / matchingResults
  → existing Matching bridge
  → persisted identity state

row click
  → matchingResult
  → optional variantResult
  → existing detail / manual accept-reject / content-label / variant-acceptance flows
```

The workspace keeps Matching identity and Variant recording status separate. Confidence remains the existing matcher value; the UI only changes its presentation from a large circle to a compact percentage + meter. Narrow desktop windows keep the side-by-side semantics through horizontal table scrolling rather than introducing a second mobile layout.

## Local Library root selection boundary

Configured Local Library roots and the Local Library view filter are separate concepts. Root management adds/removes/scans configured sources. The view filter only changes which roots participate in the Local track query.

```text
UI selected root IDs
        ↓
MusicArkBridgeClient.localTracks(rootIds)
        ↓
mvp_bridge --root-ids <JSON array>
        ↓
LocalLibraryService.tracks(root_ids)
        ↓
LocalLibraryStorageRepository.list_tracks(root_ids)
        ↓
SQLite COUNT / search / sort / LIMIT / OFFSET over the same filtered set
```

`rootIds = null` means all configured roots, `[]` means no roots, and a non-empty list means that exact root subset. The predicate is parameterized; filesystem paths are not used to build SQL. Single-root commands such as scan/remove retain their existing `rootId` contract.

## Yandex collection boundaries

`YandexLibraryService.bootstrap()` is cache-first. It exposes cached liked tracks, playlist metadata and the explicit Yandex Music liked-album index. `library_refresh()` refreshes those indexes without eagerly fetching every playlist or album. Opening one playlist or album loads that collection lazily and caches its ordered tracks.

The Albums tab is **not** derived from album tags on tracks in `Мне нравится / Liked`. It represents albums explicitly liked by the authenticated Yandex Music account through the pinned provider client. MusicArk only reads and caches this information; v0.9.x UI milestones do not like/unlike albums or otherwise mutate Yandex Music.

The album cache, Local Library root filter and v0.9.3–v0.9.7 presentation milestones all reuse existing schema `1.8.4`; no database migration is required.

## Authoritative safety boundaries

The v0.9.x shell observes existing Yandex `session` payloads; it does not create another credential store or authentication API. Theme/locale preferences remain UI-only.

The Yandex sign-in view may show a help link for obtaining an OAuth token, but the credential boundary remains unchanged: the user supplies the token explicitly, Flutter passes it only through the login bridge environment, and successful login stores it through the existing protected Windows credential store.

Controlled Sync does not implement another matcher, Coverage engine, downloader or Local indexer. It reads current state from those layers and delegates acquisition to Downloads. v0.9.6 keeps the existing confirmation and enqueue-only Apply boundaries.

Yandex playback is a user-initiated preview path. It creates/reuses a private file under `.musicark/playback/yandex`; that file is not inserted into Local Library, Matching or Coverage. Flutter receives the local playback path, never protected provider media URLs or credentials.

Metadata Editor remains the explicit ordinary write boundary. Local Scan, root selection, Matching, Coverage, Sync, content labels and variant acceptance never rewrite user audio files. ORIGINAL/CENSORED marks never mutate Yandex provider data or alter Matching identity.

v0.9.7 Help documents these boundaries but does not create new domain behavior. About diagnostics remain limited to app/backend/schema version, OS, theme and locale.

v0.15 Windows packaging produces the release-facing executable `Music Ark.exe`. The internal Flutter/CMake target name can stay technical, but installer shortcuts, package validation and Windows resource metadata must use the display name.

v1.0.0 publication readiness adds the legal distribution boundary for Windows
artifacts:

```text
LICENSE
THIRD_PARTY_NOTICES.md
licenses/
docs/releases/v1.0.0.md
docs/releases/v1.0.0_EN.md
docs/releases/v1.0.0-github.md
```

`LICENSE` applies to MusicArk's own code only. Third-party runtime components keep
their own licenses and are documented in `THIRD_PARTY_NOTICES.md`. Packaging must
copy all legal files into the portable ZIP and the Inno Setup installation
directory. MusicArk uses an unofficial Yandex Music API wrapper and is not an
official Yandex product or Yandex affiliate.

## Documentation entry points

- `docs/releases/v1.0.0.md` and `docs/releases/v1.0.0_EN.md` — public v1.0.0 release notes;
- `THIRD_PARTY_NOTICES.md` — redistributed Windows runtime component license/source inventory;
- `docs/versions/v0.9.7.md` — current Settings / Help / About UI Draft milestone and verification gate;
- `docs/versions/v0.9.6.md` — Controlled Sync presentation and safety boundaries;
- `docs/versions/v0.9.5.md` — Downloads safe deletion / bulk-action semantics;
- `docs/versions/v0.9.4.md` — Coverage / Missing UI presentation;
- `docs/versions/v0.9.3.md` — Matching UI presentation;
- `docs/versions/v0.9.2.md` — Local Library multi-root query/view semantics;
- `docs/architecture/ui-design-system.md` — shared desktop presentation rules;
- `docs/architecture/app-shell-settings.md` — shell/account/preferences/utility-page boundaries;
- `docs/architecture/metadata-editor.md` — explicit local write boundary;
- `docs/architecture/content-labels.md` — ORIGINAL/CENSORED app-level marks;
- `docs/architecture/variant-acceptance.md` — reviewed recording decisions;
- `docs/testing/manual-test-plan.md` — Windows validation;
- `docs/release/release-checklist.md` — acceptance gate.
