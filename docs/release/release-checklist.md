# Release Checklist — v0.9.0 UI, Account & Settings

This checklist is the acceptance gate for the v0.9.0 Draft candidate. It does not imply a published release, installer, package, tag or GitHub Release.

## Version / schema / Git

- [ ] Python package version is `0.9.0`.
- [ ] Flutter version is `0.9.0+1` unless an intentional build-number-only change is documented.
- [ ] SQLite schema target remains `1.8.4`; v0.9.0 does not add a music DB migration.
- [ ] v0.9.0 branch is based on the accepted v0.8.2 `main` baseline.
- [ ] Draft PR targets `main` from `agent/v0.9.0-ui-account-settings`.
- [ ] final diff contains no secrets, user data, avatar fixture from a real account, unrelated build output or mass formatting.
- [ ] README.md, README_EN.md, CHANGELOG and version docs describe the same version/scope.

## Global account / session

- [ ] logged-out state shows `Войти` / `Sign in` in the bottom sidebar account control.
- [ ] sign-in routes to the existing Yandex Music login workflow.
- [ ] cached signed-in startup shows cached account information without requiring network success.
- [ ] login updates the global account control without restart.
- [ ] account menu shows provider/account context, open-Yandex action and logout.
- [ ] logout uses the existing backend credential/session boundary.
- [ ] logout updates global shell and Yandex UI without restart.
- [ ] no independent second credential store or authentication implementation exists.
- [ ] account DTO visible to Flutter contains no token, cookie or Authorization data.

## Avatar / profile fallback

- [ ] provider account contract was checked against the pinned dependency version.
- [ ] no undocumented avatar field or Yandex URL template is invented.
- [ ] available name produces one/two initials.
- [ ] missing name produces a generic user icon.
- [ ] long displayName uses ellipsis and does not overflow the sidebar.
- [ ] avatar/profile decoration failure cannot become a login/session error.

## Settings persistence

- [ ] Settings appears in the lower utility area, separated from primary music destinations.
- [ ] preference store contains only the required UI settings and a minimal schema marker.
- [ ] theme preference survives restart.
- [ ] locale preference survives restart.
- [ ] preference persistence contains no credential or library data.

## Theme

- [ ] System / Light / Dark are available.
- [ ] switching applies without restart.
- [ ] System follows platform brightness.
- [ ] centralized Material 3 / ColorScheme theme definitions are used.
- [ ] major feature pages are manually checked in Dark mode.
- [ ] no unreadable hard-coded light/dark surfaces remain in active UI.

## Localization

- [ ] standard Flutter localization pipeline is configured with RU and EN resources.
- [ ] System / Russian / English are available and persistent.
- [ ] system `ru` resolves to Russian.
- [ ] system `en` resolves to English.
- [ ] unsupported system locale deterministically falls back to Russian.
- [ ] switching locale applies without restart.
- [ ] global navigation/account/settings/help/about are localized.
- [ ] Yandex, Local Library, Matching, Missing, Downloads, Sync, Metadata Editor, dialogs/status/empty/error UI static strings are localized for acceptance.
- [ ] provider data, filenames, paths, technical IDs and backend internal codes remain untranslated.
- [ ] ORIGINAL/CENSORED presentation is localized without changing stored internal codes or DB schema.

## Help / About

- [ ] Help works offline.
- [ ] Help covers Yandex, Local Library, Matching, Missing, Downloads, Sync and Metadata Editor.
- [ ] Help explicitly explains Matching != Variant.
- [ ] Help explicitly explains Missing != Different Version.
- [ ] Help states that Sync does not delete local-only files.
- [ ] Help distinguishes Apply Metadata from Apply + Bind.
- [ ] About shows factual MusicArk `0.9.0`, backend version and schema `1.8.4`.
- [ ] no MusicArk license name is invented.
- [ ] standard Flutter dependency license UI is used where applicable.
- [ ] copied diagnostics contain no secrets, protected URLs or library contents.
- [ ] stale visible version labels such as `MusicArk 0.3` / `MusicArk 0.8` are absent.

## Shell / UI lifetime

- [ ] Yandex page state survives theme and locale changes.
- [ ] open Yandex playlist/scope is not reset by Settings changes.
- [ ] Now Playing remains alive while Settings, Help and About are open.
- [ ] Settings/Help/About do not replace the playback engine.
- [ ] Yandex workspace retains the approximately `920 px` narrow-window safeguard.
- [ ] account control remains usable at narrow widths.
- [ ] RU and EN long labels do not introduce render overflow.

## v0.8.2 safety regression

In ordinary Scan/Matching/Coverage/Sync scenarios:

```text
modified existing user audio files = 0
Yandex provider mutations = 0
```

- [ ] Metadata Editor remains the explicit ordinary write boundary.
- [ ] Apply Metadata and Apply + Bind retain their existing separate semantics.
- [ ] Matching semantics are unchanged.
- [ ] Variant semantics are unchanged.
- [ ] Coverage/Missing semantics are unchanged.
- [ ] Download semantics are unchanged.
- [ ] Controlled Sync semantics are unchanged.
- [ ] no Yandex Upload, reverse Sync or `can_upload_tracks=true` is introduced.

## Python automated checks

From repository root:

- [ ] `python -m unittest discover -s tests -p "test_*.py" -v`.

## Flutter automated checks

From `ui/musicark_ui`:

- [ ] `flutter pub get`.
- [ ] `flutter analyze` with no accepted analyzer errors/warnings hidden by rule removal.
- [ ] `flutter test test/account_session_test.dart`.
- [ ] `flutter test test/account_control_test.dart`.
- [ ] `flutter test test/app_settings_test.dart`.
- [ ] `flutter test test/v0_9_shell_test.dart`.
- [ ] full `flutter test`.

## Windows manual acceptance

- [ ] `flutter run -d windows` starts the development application.
- [ ] cached profile / login / logout / login-again scenarios pass.
- [ ] System / Light / Dark and persistence are manually checked.
- [ ] Russian / English / System and persistence are manually checked.
- [ ] Yandex / Local / Matching / Missing / Downloads / Sync / Metadata Editor / Settings / Help / About open without layout/render exceptions.
- [ ] dark-mode scenarios from `docs/testing/manual-test-plan.md` are checked.
- [ ] localization scenarios from `docs/testing/manual-test-plan.md` are checked.

Release build, installer, MSIX, portable ZIP, signing and clean-machine packaging are **not** required by v0.9.0.

If Windows/toolchain validation is unavailable, record the relevant gates as **NOT VERIFIED**, never as passed.

## CI / PR

- [ ] GitHub Actions result is recorded as PASS / FAIL / BLOCKED / NOT RUN.
- [ ] infrastructure/billing blockers are described as infrastructure blockers, not code-test failures.
- [ ] PR verification table contains only factual command/manual results.
- [ ] the PR remains Draft while UI/localization/manual acceptance is incomplete.
- [ ] the PR is not merged automatically.
