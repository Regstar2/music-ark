# Changelog

All notable project changes are recorded here. Entries describe the current code history and do not imply a published GitHub Release unless a release/tag exists separately.

## Unreleased — v0.9.7 Draft candidate

### v0.9.7 — Settings, Help & About UI Polish

#### Added

- constrained responsive desktop layouts for Settings, Help and About;
- compact Settings auto-save status, responsive theme/language cards and a provider/account card backed by the existing account session controller;
- grouped offline Help with eleven RU/EN topics covering provider/local libraries, Matching, Variant/censorship, Missing, Downloads, Controlled Sync, Metadata Editor, artwork/playback, settings and data safety;
- explicit Help/About return path to Settings inside the existing shell without a new router;
- About product card using the existing MusicArk vector mark, responsive version/environment data, diagnostics/licenses actions and a GitHub copy-link fallback;
- utility-page layout tokens and Flutter regressions for account states, long names, Help topics/navigation, About actions and narrow desktop widths.

#### Changed

- the old Settings `General` card containing only the auto-save explanation is removed in favor of header status UI;
- utility content is capped at approximately 1180 px on wide desktops and reflows through `LayoutBuilder` rather than stretching controls across the full workspace;
- Help now documents current safety and semantic boundaries such as Identity vs Metadata/Variant, Missing vs Different Version, Apply Metadata vs Apply + Bind, ORIGINAL/CENSORED labels and Controlled Sync constraints;
- application/backend package version advances to `0.9.7`, Flutter package to `0.9.7+1`; SQLite remains `1.8.4`.

#### Safety / boundaries

- Matching/Variant/Coverage truth, Download execution, Controlled Sync planner/Apply, Metadata Editor writes, provider authentication and playback semantics are unchanged;
- Settings continues to use the existing typed UI preference store and Yandex-session-derived account state;
- About diagnostics still exclude tokens, cookies, protected URLs and library contents;
- no external URL dependency, SQLite migration, provider mutation, routing/state-management framework, Yandex Upload or reverse Sync is introduced.

#### Verification state

- source changes, RU/EN Help content and focused utility-page widget regressions are included in the v0.9.7 branch;
- Flutter analyze/tests, Python regression suite, GitHub Actions and Windows visual smoke are recorded only after they actually run against the final PR head.

## v0.9.6 — Sync Page UI Polish

#### Added

- responsive Sync header and configuration card for scope plus download target;
- status-oriented summary with current/projected local coverage and five primary metrics;
- one counted/filterable Sync plan workspace replacing multiple large operation accordions;
- wide desktop operation table plus stacked narrow-layout rows;
- theme-aware local artwork placeholder without adding provider requests or expanding the Sync payload for decoration;
- Sync presentation localization through the existing generated RU/EN localization catalog;
- Flutter regression coverage for metrics/blockers, coverage, filters, no-target state, confirmation, decisions, navigation, target selection, narrow layout and English locale.

#### Changed

- Sync plan filters are Flutter presentation state over the current operation snapshot and do not rebuild or persist a second plan;
- scope/folder changes, explicit wanted/ignored decisions and Apply continue to use the existing `SyncBridgeClient` methods and planner/application boundary;
- the primary status card now keeps the confirmation-protected Sync action and Downloads shortcut next to the information that explains the action;
- empty operation categories remain visible as compact counted filters instead of occupying full `ExpansionTile` sections;
- application/backend package version advances to `0.9.6`, Flutter package to `0.9.6+1`; SQLite remains `1.8.4`.

#### Safety / boundaries

- Controlled Sync planner rules, Coverage/Matching/Variant truth, DownloadService semantics and Metadata Editor behavior are unchanged;
- existing local files are not deleted, moved, renamed or retagged by v0.9.6 Sync;
- Yandex collections are not mutated; reverse Sync and Yandex Upload remain unimplemented;
- `DIFFERENT_VERSION` still never triggers automatic replacement;
- no SQLite migration, new provider or new state-management dependency is introduced.

#### Verification state

- source changes and focused Sync widget regressions are included in the v0.9.6 branch;
- Flutter analyze/tests, Python regression suite, GitHub Actions and Windows visual smoke are recorded only after they actually run against the final PR head.

## v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions

#### Added

- compact Downloads/Wanted tabs, four queue summary metrics, search/status filters and lazy-rendered compact track rows;
- user-friendly error messages derived from `errorCode` plus a separate technical-details dialog preserving raw backend diagnostics;
- explicit safe task removal for `failed` / `needs_review`, with confirmation and `download_task_removed` audit evidence;
- selection and bulk retry/cancel/remove actions in Downloads;
- selection plus `Download selected` in Wanted;
- one-process batch bridge commands for retry/cancel/remove/run/enqueue-selected with partial-result reporting;
- RU/EN localization for the redesigned Downloads workspace;
- Python and Flutter regression coverage for task removal, queue isolation, bulk actions, search, progress, technical details and localization.

#### Changed

- Downloads no longer builds every task as a large eager Card list; the workspace uses `CustomScrollView` / `SliverList` and denser desktop rows;
- Download-all-Wanted runs only task IDs newly added by that action rather than waking unrelated queued work;
- bulk retry runs only selected retryable task IDs; bulk selected download runs only task IDs returned by the selected enqueue action;
- existing explicit `Continue queue` remains sequential and retains the stop-after-current behavior when leaving Downloads;
- Flutter package version advances to `0.9.5+1`; SQLite remains `1.8.4`.

#### Safety / boundaries

- removing a download task deletes only the `download_tasks` record and never deletes the final audio file, Local Library, Matching, Coverage, Wanted state, provider cache or audit history;
- only the expected sibling `.part` may be removed, after a safe path check;
- queued/running tasks remain cancellation-only and cannot be directly removed;
- user bulk actions reject internal/legacy download tasks;
- no SQLite migration, new provider, new dependency, Yandex mutation or Metadata Editor/Controlled Sync behavior is introduced.

#### Verification state

- source changes and regression tests are included in the v0.9.5 branch;
- GitHub Actions Python/Flutter results and Windows visual smoke must be recorded only after they actually run against the final PR head.

## v0.9.4 — Coverage / Missing UI Polish

#### Added

- compact Coverage summary with local coverage progress, four primary metrics and collapsible Matching/Variant analysis details;
- counted Coverage status tabs, master Select All with indeterminate partial-selection state and localized list result counts;
- provider-artwork thumbnails with theme-aware local fallback that does not introduce a new cache or dependency;
- RU/EN localization for the Coverage workspace, actions, empty states, pagination feedback and details dialog;
- Flutter regression coverage for summary details, tabs, selection, artwork fallback, single-page pagination hiding, English localization and compact desktop widths.

#### Changed

- Coverage now prioritizes track rows over the previous long technical summary string and separate ChoiceChip/action rows;
- Search is the primary wide filter, Decision is shown only for Missing, and Variant filtering remains scoped to Covered results;
- track rows now render title first, artist/album second, collection badges, Coverage/Variant status badges and responsive action hierarchy;
- `Скачать / Download` remains the primary Missing action while Wanted, Ignore and Reset retain their existing triage semantics;
- pagination is hidden when the current filtered result fits within the existing 100-item page size;
- application/backend/Flutter package version advances to `0.9.4`; SQLite remains `1.8.4`.

#### Safety / boundaries

- Coverage calculation, Matching/Variant algorithms, Download execution, Controlled Sync and Metadata Editor semantics are unchanged;
- direct Download does not mutate `userAction`, and bulk selection still performs only triage actions rather than bulk-download;
- artwork uses the already persisted `ProviderTrack.artwork_url`; Flutter does not construct Yandex URLs or receive provider credentials;
- no SQLite migration or new dependency is introduced by v0.9.4.

#### Verification state

- source-level structural checks and RU/EN ARB JSON/key-parity checks were performed while preparing the branch;
- Flutter analyze/tests, Python regression suite, Windows build and Windows visual smoke must be recorded only after they actually run against the v0.9.4 PR head.

## v0.9.3 — Matching UI Redesign

#### Added

- five responsive Matching summary cards for Yandex tracks, Local tracks, matched identities, review conflicts and unmatched identities;
- counted status filters, explicit read-only refresh, compact Matching/Variant result banners and a shown-results counter;
- a fixed-header side-by-side Matching workspace with Yandex, Local, confidence and status columns;
- narrow-desktop horizontal table scrolling while retaining the comparison structure;
- RU/EN localization for the new Matching workspace and regression coverage for localized English presentation, dark theme and narrow layouts.

#### Changed

- Matching results no longer use stacked `ListTile` rows with a large confidence `CircleAvatar`; confidence is now a compact percentage plus progress meter;
- Yandex identity data and the candidate/linked local file are rendered next to each other for faster manual comparison;
- Matching identity status and Variant recording status remain separate visible badges instead of being visually conflated;
- Search/Sort/filters keep the existing backend query contract and pagination keeps the active query scope;
- conflict review, content labels, Variant recheck/acceptance and manual candidate accept/reject remain in the existing detail workflow;
- application/backend/Flutter package version advances to `0.9.3`; SQLite remains `1.8.4`.

#### Localization

- all new Matching header, summary, action, filter, search, table, status, empty-state and pagination strings are provided through existing RU/EN `gen_l10n` resources;
- provider/user metadata, paths, filenames and backend error payloads remain untranslated;
- unchanged legacy detail-dialog strings are not expanded into an unrelated full localization rewrite in this version.

#### Safety / boundaries

- Matching/Variant algorithms, confidence computation, candidate generation and bridge semantics are unchanged;
- Matching and Variant analysis remain non-mutating for existing user audio files;
- manual identity decisions, content labels and Variant acceptance continue to update MusicArk state only within their existing boundaries;
- no per-row Yandex artwork request, new artwork cache or SQLite migration is introduced by v0.9.3.

#### Verification state

- source-level structural checks and RU/EN ARB JSON/key-parity checks were performed while preparing the branch;
- Flutter analyze/tests, Python regression suite, Windows build and Windows visual smoke must be recorded only after they actually run against the v0.9.3 PR head.

## v0.9.2 — Local Library UI & Multi-Root Selection

#### Added

- a true Local Library multi-root view filter that can represent all configured roots, one root, an arbitrary subset, or no roots;
- typed `rootIds` query plumbing from Flutter through `mvp_bridge` and `LocalLibraryService` into SQLite;
- parameterized multi-root `IN (...)` filtering before `COUNT`, search, sort, `LIMIT` and `OFFSET`;
- root-selection reconciliation for add/remove operations, including auto-selection of a newly added root only when the previous state represented all roots;
- dedicated Local Library empty states for no configured roots, no selected roots and no search results;
- Python regression coverage for all/one/multiple/empty root sets, combined search/sort/pagination and invalid process-boundary input;
- Flutter regression coverage for root selection, select-all, empty selection, pagination/search/sort preservation and add/remove reconciliation.

#### Changed

- Local Library now uses the shared v0.9.x desktop presentation hierarchy: page header, responsive toolbar, compact root-management section and responsive track rows;
- root management is visually and semantically separate from the root view filter;
- wide Local track rows expose artwork, title/artist, album, year, format, ORIGINAL/CENSORED, duration and compact actions; narrower desktop layouts collapse secondary metadata without changing functionality;
- ORIGINAL/CENSORED presentation remains editable from the status control while secondary file/details actions move into overflow;
- routine successful scan feedback is compact, while scan errors remain explicit;
- application/backend/Flutter package version advances to `0.9.2`; SQLite remains `1.8.4`.

#### Localization

- all new Local Library filter, table, folder-management, scan-status and empty-state strings are provided through existing RU/EN `gen_l10n` resources;
- paths, filenames, track/provider metadata, codecs, IDs and backend codes remain untranslated.

#### Safety / boundaries

- multi-root selection is query/view state only and does not modify configured roots unless the user explicitly uses root-management actions;
- Local Scan, Matching, Coverage and Controlled Sync remain non-mutating for existing user audio files;
- Metadata Editor remains the explicit ordinary write boundary for an existing local file;
- ORIGINAL/CENSORED labels remain MusicArk-local state and do not mutate Yandex Music or audio metadata;
- no SQLite migration is introduced for v0.9.2.

#### Verification state

- source-level Python syntax compilation and localization-resource JSON/key-parity checks were performed while preparing the branch;
- GitHub Actions Python/Flutter suites and Windows visual smoke must be recorded only after they actually run against the v0.9.2 PR head.

## v0.9.1 — Main Screen UI Polish

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
- the normal provider status `available` is no longer rendered on every track. unavailable tracks remain distinguishable and have playback disabled with an explanatory tooltip;
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
