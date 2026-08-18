# MusicArk Desktop UI System

This document describes the small presentation layer introduced for v0.9.1 and extended through the v0.9.x Local Library, Matching, Coverage, Downloads, Sync and utility-page slices. It is not a separate framework and does not own music-domain state.

## Principles

1. One permanent application navigation surface.
2. Music content receives the majority of horizontal space.
3. Provider-specific navigation lives inside the provider workspace, not in a second permanent sidebar.
4. Normal states are quiet; exceptional/actionable states are visually explicit.
5. Light and Dark derive from the same Material 3 `ColorScheme`.
6. Desktop resizing is responsive without pretending the application is a mobile UI.
7. Feature bridges remain explicit application dependencies; presentation must not infer capabilities from wrapper runtime types.
8. View filters change presentation/query scope only; source-management actions remain separate explicit controls.
9. Presentation-only filters over already loaded snapshots must not silently create new backend/domain state.
10. Utility pages constrain reading width on large desktops and reflow controls on narrower windows instead of stretching sparse content edge to edge.

## Shared tokens

`lib/app_ui_tokens.dart` centralizes the limited constants that are genuinely shared:

- global sidebar width;
- page/section/compact spacing;
- track row and artwork sizes;
- common radii;
- icon size;
- Yandex toolbar/table responsive breakpoints;
- utility-page max content width and reflow thresholds.

Colors are not duplicated in this file. Widgets obtain semantic colors from `Theme.of(context).colorScheme`.

## Global sidebar

The global shell is the only permanent sidebar. It contains primary music destinations and keeps Settings/Account in the utility area at the bottom. A small theme-aware MusicArk mark is painted in Flutter, avoiding a dependency or asset pipeline solely for one icon.

## Utility pages — v0.9.7

Settings, Help and About use the same desktop presentation principles as the music workspaces while remaining visually quieter.

```text
shell available width
        ↓
page padding
        ↓
centered utility content (max ≈ 1180 px)
        ↓
responsive cards/rows
```

Settings keeps labels/descriptions on the left and segmented controls on the right when enough space is available. Below the utility-row breakpoint, controls move below the description rather than forcing horizontal overflow.

Help uses grouped expansion rows. Closed rows show a title plus one short summary; expanded content contains the detailed offline explanation. It does not introduce nested accordions or a web-help dependency.

About uses the existing `MusicArkMark`, a product card, responsive version/environment information, diagnostics/licenses actions and a repository copy-link action. The environment layout changes from two columns to one below the utility-grid breakpoint.

Help and About show an explicit return path to Settings, but navigation still uses the existing application shell index. No router/state-management framework is introduced for utility pages.

## Yandex workspace

Top-level provider navigation uses three conceptual destinations:

```text
Tracks / Liked
Playlists
Albums
```

Opening a playlist or album creates a detail state inside the same workspace. It does not create or restore a nested permanent sidebar.

The collection header owns title, count, human-readable update time/source and refresh. Search/sort/version-label management form the collection toolbar.

## Local Library workspace

v0.9.2 applies the same desktop hierarchy to Local Library:

```text
page header + primary actions
        ↓
search + root selection + sort toolbar
        ↓
compact library-root management
        ↓
responsive track table/list
```

The folder selector is a **view filter**, not root management. It stores canonical root IDs and can represent:

```text
all roots
one root
arbitrary subset
no roots
```

The persistent selector dialog uses Material `CheckboxListTile` controls with a tri-state master checkbox for partial selection. Applying the dialog triggers a backend query for the selected root IDs; Flutter does not filter only the currently loaded page.

Configured roots are managed separately in a compact source section with per-root scan and remove actions. Removing a root still uses the existing explicit index-only confirmation.

## Sync workspace

v0.9.6 applies the same hierarchy to Controlled Sync without changing the Sync domain model:

```text
page header + refresh
        ↓
responsive scope + target-folder configuration
        ↓
status + primary action
        ↓
current/projected coverage + five primary metrics
        ↓
counted presentation filters
        ↓
responsive operation table/list
```

The plan filters are local Flutter state over the operations returned by the current plan. Switching `All / Download / Decision / Matching / Variant / Local-only` does **not** call `createPlan`, persist a new plan or modify user actions.

Scope/folder changes, explicit `wanted`/`ignored` decisions and Apply keep using the existing bridge/application boundary. Apply still rebuilds the current diff and requires explicit confirmation before enqueueing valid downloads.

Sync operation metadata does not gain an artwork dependency for v0.9.6. If artwork is absent, the row uses a theme-aware local music placeholder. A decorative image is not a reason to add provider requests or expose credentials.

## Track rows

Wide workspace:

```text
artwork | title + artist | album/secondary data | status | actions
```

Compact workspace:

```text
artwork | title + artist/secondary data | optional status | actions
```

Normal provider/local metadata is quiet. ORIGINAL/CENSORED remains visible as a compact editable chip when set. Stored values remain `original` / `censored`; localization affects presentation only.

Local Library primary row actions are Play and Metadata Editor where available. Details and reveal-in-filesystem remain accessible through the secondary overflow menu and row detail view.

Sync uses a similar visual density but preserves its own operation semantics: action/category, reason and status/contextual action remain visible; no destructive row action is introduced.

## Responsive rules

`LayoutBuilder` selects wide versus compact composition from the space actually provided by the shell. Toolbars and utility actions reflow instead of forcing page-wide horizontal scrolling.

The target validation sizes are:

- 1920×1080;
- 1600×900;
- 1366×768;
- a narrow desktop application window around 900 px wide;
- focused feature-widget tests may use narrower surfaces to guard against `RenderFlex` overflow.

Text that can grow from provider/user data uses ellipsis when the value is recoverable elsewhere. Important About environment values wrap instead of being silently discarded. Paths keep their full value available through tooltips/detail surfaces.

The v0.9.6 Sync plan uses a wide table when enough content width is available and stacked operation rows below that threshold. Counted plan filters remain horizontally scrollable rather than shrinking text/actions into invalid constraints.

## Now Playing

The application-wide player remains below the shell page stack. v0.9.1 only changes its composition: artwork placeholder, title/artist presentation, Play/Pause, progress/time and stop/close reflow at narrower widths. No queue/next/previous/shuffle/repeat semantics are introduced.

Utility navigation in v0.9.7 does not replace or recreate Now Playing.

## Localization

UI presentation strings use the existing generated RU/EN `gen_l10n` resources. Provider data, local paths, filenames, track metadata and technical IDs are not translated.

v0.9.6 keeps `SyncPage` free of hard-coded user-facing Russian text through a small `SyncLocalizations` adapter over the existing generated catalog. This adapter is presentation-only and is not a second localization store.

v0.9.7 expands the same generated catalog for Settings/Help/About; no utility-page localization store is introduced.

## Non-goals

This presentation layer does not change:

- Matching algorithms or confidence;
- Variant analysis/classification;
- Coverage truth;
- Download execution semantics;
- Controlled Sync planner/Apply semantics;
- Metadata Editor write semantics;
- authentication/credential storage;
- SQLite schema;
- Yandex provider mutation behavior.
