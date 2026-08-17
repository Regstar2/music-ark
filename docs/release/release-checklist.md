# Release Checklist — v0.9.1 Main Screen UI Polish

This checklist is the acceptance gate for the v0.9.1 Draft candidate. It does not imply a published release, installer, package, tag or GitHub Release.

## Version / schema / Git

- [ ] Python package version is `0.9.1`.
- [ ] Flutter version is `0.9.1+1`.
- [ ] SQLite schema target remains `1.8.4`; v0.9.1 adds no music DB migration.
- [ ] branch is based on current accepted `main`.
- [ ] Draft PR targets `main` from `agent/v0.9.1-main-ui-polish`.
- [ ] final diff contains no secrets, user data, build output or unrelated mass formatting.
- [ ] README.md, README_EN.md, CHANGELOG and version docs describe the same version/scope.

## Single navigation architecture

- [ ] global MusicArk sidebar is the only permanent application sidebar.
- [ ] old permanent Yandex nested sidebar is absent.
- [ ] Yandex Tracks, Playlists and Albums remain reachable via top-level workspace navigation.
- [ ] playlist detail has explicit back navigation.
- [ ] album detail has explicit back navigation.
- [ ] Settings and Account remain in the global utility area.
- [ ] theme-aware MusicArk mark/title render in Light and Dark modes without overflow.
- [ ] Settings ListTile does not trigger the Flutter background/ink assertion.

## Yandex workspace

- [ ] collection header shows title, count, human-readable update time and source.
- [ ] refresh remains available.
- [ ] track search works for title/artist/album.
- [ ] Yandex/title/artist sorting preserves previous semantics.
- [ ] `Unavailable first / Недоступные сначала` places unavailable tracks before available tracks without changing provider state.
- [ ] playlist search and sort remain available.
- [ ] Albums shows the authenticated user's explicit Yandex Music album likes, not albums inferred from liked-track metadata.
- [ ] album index is cache-first and album contents are fetched lazily when a specific album is opened.
- [ ] album detail contains the full provider album track list, not only tracks from `Liked / Мне нравится`.
- [ ] unliking an album in Yandex and refreshing removes it from the active liked-album index without deleting unrelated cached collections.
- [ ] album read paths do not like/unlike or otherwise mutate Yandex Music.
- [ ] artwork loading and fallback remain available in track and album presentation.
- [ ] normal `available` text is not shown on every track.
- [ ] unavailable track playback is disabled and explained through tooltip/presentation.

## ORIGINAL / CENSORED regression

- [ ] `ContentLabelBridgeClient` remains an explicit feature dependency.
- [ ] session-aware bridge wrapping cannot disable label controls.
- [ ] inline ORIGINAL chip renders.
- [ ] inline CENSORED chip renders.
- [ ] inline label menu changes a label.
- [ ] label can be removed.
- [ ] general `Version labels / Пометки версий` manager remains available from the toolbar.
- [ ] standalone label/control tests have deterministic localization setup.
- [ ] labels still do not mutate Yandex metadata, audio tags, identity or confidence.

## Responsive desktop

Check at least:

```text
1920×1080
1600×900
1366×768
~900 px narrow desktop application window
```

- [ ] no `RenderFlex overflow`.
- [ ] no ListTile background/ink assertion.
- [ ] no ListTile/trailing width assertion in About.
- [ ] toolbar reflows instead of requiring old ~920 px forced horizontal workspace.
- [ ] title and album use ellipsis where needed.
- [ ] labeled compact rows remain usable.
- [ ] row actions remain reachable.
- [ ] playlist and album navigation remain usable.
- [ ] global sidebar brand/account/settings remain usable.

## Localization / injected-test isolation

- [ ] RU and EN resources describe explicitly liked albums accurately.
- [ ] Yandex tabs including Albums, back navigation, search/sort/unavailable-first, version-label/table/empty-state/availability UI change language without restart.
- [ ] unsupported system locale uses deterministic Russian fallback.
- [ ] injected fake-bridge tests do not read the developer machine's persisted UI settings unless a settings storage is explicitly supplied.
- [ ] injected fake-bridge tests do not start the production content-label subprocess unless a content-label bridge is explicitly supplied.

## Account / session regression

- [ ] cached signed-in account remains cache-first.
- [ ] failed network refresh does not visually log a cached session out.
- [ ] login/logout continue through existing Yandex credential/session boundaries.
- [ ] no second account implementation or credential store is introduced.
- [ ] account control remains global, not duplicated inside Yandex workspace.

## Now Playing

- [ ] player remains application-wide and survives ordinary page navigation.
- [ ] Play/Pause, progress/seek, elapsed/duration and stop/close remain available.
- [ ] compact player layout does not overflow at narrow desktop width.
- [ ] no queue/next/previous/shuffle/repeat semantics are introduced in v0.9.1.

## v0.8.2/v0.9.0 safety regression

In ordinary Scan/Matching/Coverage/Sync scenarios:

```text
modified existing user audio files = 0
Yandex provider mutations = 0
```

- [ ] Metadata Editor remains the explicit ordinary write boundary.
- [ ] Apply Metadata and Apply + Bind retain separate semantics.
- [ ] Matching semantics are unchanged.
- [ ] Variant semantics are unchanged.
- [ ] Coverage/Missing semantics are unchanged.
- [ ] Download semantics are unchanged.
- [ ] Controlled Sync semantics are unchanged.
- [ ] no Yandex Upload or reverse Sync is introduced.

## Automated checks

From repository root:

- [ ] `python -m unittest discover -s tests -p "test_*.py" -v`.

From `ui/musicark_ui`:

- [ ] `flutter pub get`.
- [ ] `flutter analyze`.
- [ ] `flutter test test/widget_test.dart`.
- [ ] `flutter test test/feature_bridge_wiring_test.dart`.
- [ ] `flutter test test/v0_9_shell_test.dart`.
- [ ] `flutter test test/v0_9_1_content_labels_test.dart`.
- [ ] `flutter test test/v0_9_1_responsive_test.dart`.
- [ ] `flutter test test/v0_9_1_localization_test.dart`.
- [ ] `flutter test test/yandex_content_label_test.dart`.
- [ ] `flutter test test/yandex_track_controls_test.dart`.
- [ ] `flutter test test/yandex_narrow_layout_test.dart`.
- [ ] full `flutter test`.

## Windows visual/manual acceptance

- [ ] `flutter run -d windows` starts the development application.
- [ ] 1920×1080 / 1600×900 / 1366×768 / narrow desktop resize are checked.
- [ ] Light and Dark are manually inspected.
- [ ] Russian and English are manually inspected.
- [ ] Tracks / Playlists / liked Albums / detail / search / sort / unavailable-first / refresh / artwork / playback / labels are checked.
- [ ] global account login/logout and Now Playing lifetime are checked.
- [ ] Local / Matching / Missing / Downloads / Sync / Metadata Editor still open and behave as before.

Release build, installer, MSIX, portable ZIP, signing and clean-machine packaging are **not** required by v0.9.1.

If Windows/toolchain validation is unavailable, record the relevant gates as **NOT VERIFIED**, never as passed.

## CI / PR

- [ ] GitHub Actions result is recorded factually as PASS / FAIL / BLOCKED / NOT RUN / NOT VERIFIED.
- [ ] PR verification table contains only real command/manual results.
- [ ] PR remains Draft until owner visual acceptance.
- [ ] PR is not merged automatically.
