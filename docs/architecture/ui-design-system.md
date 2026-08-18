# MusicArk Desktop UI System

This document describes the small presentation layer introduced for v0.9.1 and extended to Local Library in v0.9.2. It is not a separate framework and does not own music-domain state.

## Principles

1. One permanent application navigation surface.
2. Music content receives the majority of horizontal space.
3. Provider-specific navigation lives inside the provider workspace, not in a second permanent sidebar.
4. Normal states are quiet; exceptional/actionable states are visually explicit.
5. Light and Dark derive from the same Material 3 `ColorScheme`.
6. Desktop resizing is responsive without pretending the application is a mobile UI.
7. Feature bridges remain explicit application dependencies; presentation must not infer capabilities from wrapper runtime types.
8. View filters change presentation/query scope only; source-management actions remain separate explicit controls.

## Shared tokens

`lib/app_ui_tokens.dart` centralizes the limited constants that are genuinely shared:

- global sidebar width;
- page/section/compact spacing;
- track row and artwork sizes;
- common radii;
- icon size;
- Yandex toolbar/table responsive breakpoints.

Colors are not duplicated in this file. Widgets obtain semantic colors from `Theme.of(context).colorScheme`.

## Global sidebar

The global shell is the only permanent sidebar. It contains primary music destinations and keeps Settings/Account in the utility area at the bottom. A small theme-aware MusicArk mark is painted in Flutter, avoiding a dependency or asset pipeline solely for one icon.

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

## Track rows

Wide workspace:

```text
artwork | title + artist | album | year | format | label | duration | actions
```

Compact workspace:

```text
artwork | title + artist/album/year/format/duration | optional label | actions
```

Normal provider/local metadata is quiet. ORIGINAL/CENSORED remains visible as a compact editable chip when set. Stored values remain `original` / `censored`; localization affects presentation only.

Local Library primary row actions are Play and Metadata Editor where available. Details and reveal-in-filesystem remain accessible through the secondary overflow menu and row detail view.

## Responsive rules

`LayoutBuilder` selects wide versus compact composition from the space actually provided by the shell. Toolbars reflow instead of forcing page-wide horizontal scrolling.

The target validation sizes are:

- 1920×1080;
- 1600×900;
- 1366×768;
- a narrow desktop application window around 900 px wide.

Text that can grow from provider/user data uses ellipsis. Paths keep their full value available through tooltips/detail surfaces.

## Now Playing

The application-wide player remains below the shell page stack. v0.9.1 only changes its composition: artwork placeholder, title/artist presentation, Play/Pause, progress/time and stop/close reflow at narrower widths. No queue/next/previous/shuffle/repeat semantics are introduced.

## Localization

All strings introduced by v0.9.1/v0.9.2 UI slices use `gen_l10n` RU/EN resources. Provider data, local paths, filenames, track metadata and technical IDs are not translated.

## Non-goals

This presentation layer does not change:

- Matching;
- Variant analysis;
- Coverage;
- Download;
- Controlled Sync;
- Metadata Editor write semantics;
- authentication/credential storage;
- SQLite schema;
- Yandex provider mutation behavior.
