# MusicArk Desktop UI System

This document describes the small presentation layer introduced for v0.9.1. It is not a separate framework and does not own music-domain state.

## Principles

1. One permanent application navigation surface.
2. Music content receives the majority of horizontal space.
3. Provider-specific navigation lives inside the provider workspace, not in a second permanent sidebar.
4. Normal states are quiet; exceptional/actionable states are visually explicit.
5. Light and Dark derive from the same Material 3 `ColorScheme`.
6. Desktop resizing is responsive without pretending the application is a mobile UI.
7. Feature bridges remain explicit application dependencies; presentation must not infer capabilities from wrapper runtime types.

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

Top-level provider navigation uses two conceptual destinations:

```text
Tracks / Liked
Playlists
```

Opening a playlist creates a detail state inside the same workspace. It does not create or restore a nested permanent sidebar.

The collection header owns title, count, human-readable update time/source and refresh. Search/sort/version-label management form the collection toolbar.

## Track rows

Wide workspace:

```text
artwork | title + artist | album | label | duration | actions
```

Compact workspace:

```text
artwork | title + artist/album/duration | optional label | actions
```

Normal provider availability is implicit. An unavailable track is visually de-emphasized, has disabled playback and exposes an explanatory tooltip.

ORIGINAL/CENSORED remains visible as a compact chip when set. The stored values remain `original` / `censored`; localization affects presentation only.

## Responsive rules

`LayoutBuilder` selects wide versus compact composition from the space actually provided by the shell. The redesigned Yandex workspace does not require the historical fixed ~920 px horizontal-scroll safeguard.

The target validation sizes are:

- 1920×1080;
- 1600×900;
- 1366×768;
- a narrow desktop application window around 900 px wide.

Text that can grow from provider/user data uses ellipsis. Toolbars reflow rather than extending the page horizontally.

## Now Playing

The application-wide player remains below the shell page stack. v0.9.1 only changes its composition: artwork placeholder, title/artist presentation, Play/Pause, progress/time and stop/close reflow at narrower widths. No queue/next/previous/shuffle/repeat semantics are introduced.

## Localization

All strings introduced by this UI slice use `gen_l10n` RU/EN resources. Provider data, track metadata, filenames and technical IDs are not translated.

## Non-goals

This presentation layer does not change:

- Matching;
- Variant analysis;
- Coverage;
- Download;
- Controlled Sync;
- Metadata Editor;
- authentication/credential storage;
- SQLite schema;
- Yandex provider mutation behavior.
