# Changelog

All notable project changes are recorded here. Entries describe the current code history and do not imply a published GitHub Release unless a release/tag exists separately.

## Unreleased — v0.9.1 Draft candidate

### v0.9.1 — Main Screen UI Polish

#### Added

- shared desktop UI layout tokens for sidebar width, page spacing, control density, artwork size, row height and responsive breakpoints;
- a theme-aware vector MusicArk mark rendered directly by Flutter;
- a third Yandex workspace tab, Albums, backed by the authenticated user's actual Yandex Music liked-album collection;
- cache-first liked-album index storage plus lazy per-album track snapshots using the existing generic provider-collection tables, with no SQLite schema bump;
- album grid/detail navigation with artwork, album title, artist summary, search and explicit back navigation;
- an `Unavailable first` / `Недоступные сначала` track sort mode based on the existing provider availability value;
- responsive Yandex workspace tests for wide, 1366×768-class and narrower desktop sizes;
- regression coverage for the single global sidebar, Liked/Playlists/Albums navigation, playlist and album detail/back, hidden normal availability text and ORIGINAL/CENSORED feature wiring.

#### Changed

- removed the second permanent Yandex Music sidebar; the global MusicArk sidebar is now the only permanent application navigation surface;
- Liked tracks, Playlists and explicitly liked Albums now use top-level segmented navigation inside the Yandex workspace;
- opened playlists and albums use detail views with explicit back navigation instead of returning to a nested sidebar;
- Yandex search, sort and version-label controls now reflow responsively instead of relying on the old approximately `920 px` forced workspace with horizontal scrolling;
- track rows use a table-like desktop layout when wide and a compact responsive layout when narrow;
- the normal provider status `available` is no longer rendered on every row; unavailable tracks remain distinguishable and have playback disabled with an explanatory tooltip;
- the general ORIGINAL/CENSORED manager moved into the collection toolbar while inline chips and row editing remain available;
- injected Flutter test applications now use isolated default settings and do not launch the production content-label subprocess unless that dependency is explicitly supplied;
- the global sidebar received a compact branded presentation and consistent selected/hover surfaces;
- Now Playing received responsive presentation while retaining the existing application-wide player lifetime and playback semantics;
- Python version advanced to `0.9.1` and Flutter version to `0.9.1+1`; SQLite remains `1.8.4`.

#### Fixed

- the Settings `ListTile` now paints against a Material ancestor instead of an intermediate `ColoredBox`, eliminating the Flutter ink/background assertion;
- the MusicArk brand row can shrink safely inside the 200 px sidebar and no longer overflows horizontally;
- About information rows switch to a stacked layout on narrow content widths instead of using a trailing widget that can consume the whole tile width;
- standalone Yandex label/control widget tests install the application localization delegates and deterministic locale they require;
- full-app tests no longer inherit the developer machine's persisted locale/theme settings when a fake main bridge is injected;
- full-app tests no longer trigger a real Python content-label subprocess when that feature bridge was not explicitly injected;
- the legacy narrow-Yandex regression test no longer expects the removed nested sidebar and fixed horizontal viewport;
- legacy in-process `mvp_bridge` helper functions are retained while adding liked-album bridge commands.

#### Localization

- all newly introduced v0.9.1 Yandex workspace, toolbar, table, playlist/album navigation, availability and label-manager strings are provided through RU/EN localization resources;
- provider data, titles, artists, album names, filenames, technical IDs and backend internal values remain untranslated.

#### Safety / boundaries

- Albums are read from the user's Yandex Music liked-album collection through the pinned `yandex-music` client; MusicArk only reads/caches this data and does not modify provider album likes;
- the album cache reuses existing provider collection storage and does not add a music-database migration;
- `ContentLabelBridgeClient` and metadata feature bridges remain explicit shell dependencies and are not inferred from the concrete runtime type of the session-aware Yandex bridge;
- Matching, Variant, Coverage, Download, Controlled Sync, Metadata Editor, provider authentication, credential storage and file-mutation rules are unchanged;
- Yandex Upload and reverse Sync remain outside v0.9.1.

#### Verification state

- the user-run Python `unittest` suite on the pre-fix v0.9.1 head passed 213 tests in 19.727 seconds;
- `flutter pub get` passed and the Windows debug application built and launched on that pre-fix head;
- that Flutter run exposed deterministic-locale, test-side subprocess and stale-expectation failures which are addressed in the current source but require a fresh run before being marked PASS;
- Windows visual smoke and final Flutter verification must only be marked PASS after real execution against the final branch/PR head.

## v0.9.0 — UI, Account & Settings

### Added

- global account/profile control in the lower utility area of the application sidebar, driven by existing Yandex session payloads;
- cache-first Flutter account state with display-name initials and generic icon fallback without exposing provider credentials;
- Settings with persisted `System / Light / Dark` theme preference and `System / Russian / English` locale preference;
- centralized Material 3 light/dark themes, standard Flutter `gen_l10n`/ARB localization infrastructure, offline Help and factual About/diagnostics;
- Flutter regression coverage for account state/control, settings persistence, locale fallback, theme/locale switching and utility-page shell lifetime.

### Safety / boundaries

- login/logout reuse the existing Yandex application/credential boundary;
- UI preferences are stored separately from the MusicArk SQLite database and contain no tokens or library contents;
- Matching, Variant, Coverage, Download, Controlled Sync and Metadata Editor semantics are unchanged;
- SQLite remains `1.8.4`.

## v0.8.2 — Local Metadata Editor & Yandex Metadata Import

### Added

- explicit Metadata Editor for existing local MP3/ID3 files with structured/advanced fields, artwork replacement/removal and safe filename editing;
- transactional same-directory copy → write → MPEG/read-back validation → atomic replace pipeline;
- single-file reindex, SHA-256 refresh and targeted Matching refresh after a successful metadata write;
- backend-only Yandex Track search with Compare, selective Apply Metadata and explicit Apply + Bind;
- app-level ORIGINAL/CENSORED labels, reviewed-variant acceptance and Yandex Library artwork/playback;
- schema migrations through `1.8.4`.

### Safety / boundaries

- Scan, Matching, Coverage and Controlled Sync remain read-only for existing user audio files;
- content labels do not mutate Yandex, audio tags, identity or confidence;
- variant acceptance does not rewrite analyzer status;
- Yandex playback keeps credentials and protected provider media URLs out of Flutter.

## v0.8.1 — Rich Yandex download metadata / provenance

- Yandex downloads write available standard MP3 metadata and trusted MusicArk/Yandex provenance before atomic finalization;
- download materialization keeps the `.part → validate → metadata → atomic final` sequence;
- artwork enrichment is best-effort and existing user files are not overwritten by filename collision;
- schema advanced to `1.8.1`.

## v0.8.0 — Controlled Sync

- added persisted read-only Sync plans, staleness detection, explicit-confirmation enqueue-only Apply and production `DownloadService` delegation;
- `DIFFERENT_VERSION` never triggers automatic replacement and local-only files remain informational;
- local delete/move/rename/tag edits and Yandex mutations remain out of scope;
- schema advanced to `1.8.0`.

## v0.7.0 — Download + Local Playback

- added production `DownloadService`, persistent queue/target, authorized provider transfer, recovery, Downloads UI and embedded Local Playback; schema `1.7.0`.

## v0.6.0 — Missing Tracks / Library Coverage

- added SQL-backed `covered / missing / needs_review / not_analyzed` Coverage and independent `wanted / ignored / unreviewed` triage; schema `1.6.0`.

## v0.5.1 — Variant / Altered Track Detection

- added independent `SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED` recording/version analysis; schema `1.5.0`.

## v0.5.0 — Identity Matching

- added precision-first persisted identity matching, conflicts/manual decisions and fingerprints; schema `1.4.0`.

## v0.4.0 — Local Library

- added multiple roots, read-only incremental indexing and Local Library UI; schema `1.3.0`.

## v0.3.0 — Yandex Library / Playlists

- added cache-first Liked/playlists metadata/content and active collection snapshots; schema `1.2.0`.

## v0.2.0 — Persistent Library

- added secure credential persistence and persistent Liked cache; schema `1.1.x`.

## v0.1.0 — Verified Yandex Likes MVP

- added focused Flutter sign-in/Liked UI, Python bridge and initial Yandex provider/storage flow.
