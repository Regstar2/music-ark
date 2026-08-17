# Manual Test Plan — MusicArk v0.9.0 UI, Account & Settings

Use Windows with a controlled copy of the existing MusicArk state. Do **not** delete/reset the real `.musicark\musicark.db`, credentials, user audio, matching/variant/coverage/download/sync history, or a user's only copy of a test track.

Current code version: `0.9.0`. Current schema target: `1.8.4`.

v0.9.0 does not introduce a database migration and does not change the v0.8.2 music semantics. Its primary validation target is the desktop shell, global account state, theme, locale, Help/About and presentation regressions.

## Preconditions

- keep a valid cached Yandex session when testing signed-in startup;
- keep a logged-out scenario available;
- have cached Yandex Likes/playlists and a valid Local Library root;
- keep representative Matching, Variant, Coverage, Download and Sync state from v0.8.2;
- use a **copy** of an MP3 for every Metadata Editor write scenario;
- use a normal desktop window and at least one narrow-window scenario below the Yandex workspace width.

## Profile / account

### Cached signed-in startup

1. Start MusicArk with an existing valid stored Yandex credential and cached account.
2. Confirm the global account control at the bottom of the left sidebar immediately shows the cached display name without requiring a successful network refresh.
3. Confirm initials are shown when no verified avatar URI is available.
4. Disconnect network and restart.
5. Confirm network failure does not visually convert the saved session to logged out.

### Logged-out startup

1. Start without a stored session.
2. Confirm the bottom account control shows `Войти` / `Sign in`.
3. Click it.
4. Confirm MusicArk opens the existing Yandex Music page/login workflow rather than a second authentication screen.

### Login / logout synchronization

1. Sign in through the existing Yandex flow.
2. Confirm the global account control updates without restart.
3. Open the account popup.
4. Confirm it contains account/provider information, `Открыть Яндекс Музыку` and `Выйти`.
5. Choose logout.
6. Confirm the Yandex page and global account control both become logged out without restart.
7. Sign in again and confirm both update immediately.

### Long/missing names

- use a long displayName and verify ellipsis/no overflow;
- use a one-word name and verify one initial;
- use a two-word name and verify two initials;
- use missing displayName and verify the generic user icon.

## Settings

Open `Настройки` / `Settings` from the utility area below the main navigation destinations.

Verify sections for appearance, language, Yandex account, Help and About are reachable and do not replace the main application shell.

## Theme

Test all values:

```text
System
Light
Dark
```

For each:

1. switch the setting;
2. confirm the active UI changes without restart;
3. navigate through major pages;
4. restart MusicArk;
5. confirm the preference persists.

For `System`, change Windows light/dark appearance and confirm the application follows system brightness.

## Dark mode regression

In Dark mode inspect at least:

- Yandex track rows and playlist sidebar;
- Local Library rows;
- Matching and Variant detail/dialogs;
- Missing/Coverage;
- Downloads;
- Controlled Sync;
- Metadata Editor;
- Now Playing;
- Settings;
- Help;
- About;
- account popup.

Reject the build for unreadable foreground/background combinations, invisible dividers, disabled controls that disappear, or hard-coded light surfaces.

## Language

Test:

```text
System
Russian
English
```

1. switch language without restart;
2. verify global navigation/account/settings/help/about change language;
3. open all active feature pages and record any remaining legacy hard-coded language;
4. restart and confirm persistence;
5. set Windows locale to Russian and verify `System` resolves to Russian;
6. set Windows locale to English and verify `System` resolves to English;
7. use another system locale and verify deterministic Russian fallback.

A Settings-only language switch is **not** sufficient for acceptance. Full v0.9.0 acceptance requires the active Flutter UI static strings to use localization resources.

Provider/track metadata, filenames, paths, technical IDs and backend internal codes are not translated.

## Help

Open Help and confirm local/offline topics exist for:

- Яндекс Музыка / Yandex Music;
- Local Library;
- Matching;
- Missing;
- Downloads;
- Sync;
- Metadata Editor.

Explicitly verify the text explains:

```text
Matching != Variant
Missing != Different Version
Sync does not delete local-only files
Apply Metadata != Apply + Bind
```

Disconnect network and confirm Help still works.

## About / diagnostics

1. Open About.
2. Confirm MusicArk version is `0.9.0`.
3. Confirm backend version is `0.9.0` and database schema is `1.8.4`.
4. Confirm repository information is factual.
5. Confirm no invented MusicArk license is shown.
6. Open standard dependency licenses.
7. Copy diagnostic information and inspect clipboard content.
8. Confirm diagnostics do **not** contain token, cookies, Authorization data, protected media URLs, library filenames or file lists.
9. Search visible UI for stale labels such as `MusicArk 0.3` or `MusicArk 0.8`.

## Now Playing / shell lifetime

1. Start playback.
2. Open Settings, Help and About.
3. Change theme and language.
4. Confirm playback is not stopped merely by those UI operations.
5. Open a Yandex playlist, switch theme/language and confirm the selected playlist is preserved.
6. Logout and confirm provider-specific Yandex state is allowed to reset to the logged-out state.

## Narrow window

Resize the application below the normal Yandex workspace width.

Expected:

- the Yandex workspace keeps its approximately `920 px` minimum layout and becomes horizontally scrollable;
- global account avatar/control remains usable;
- long account names use ellipsis;
- no `RenderFlex overflow`;
- no `ListTile` trailing-width assertion/crash;
- no unhandled render exception.

This remains a desktop safeguard, not a mobile redesign.

## v0.8.2 file-mutation regression

Recheck the existing safety contract:

```text
Scan     → read-only user audio
Matching → read-only user audio
Coverage → read-only user audio
Sync     → no user audio mutation
```

Metadata Editor remains the explicit ordinary write boundary. Use a copied MP3 to verify Apply Metadata and Apply + Bind still preserve their v0.8.2 distinction.

## Matching / Variant / Missing regression

Verify:

- Matching still answers track identity and does not absorb Variant semantics;
- ORIGINAL/CENSORED remains an app-level label and does not change DB/provider codes for localization;
- Missing remains distinct from Different Version;
- unresolved Variant results retain their previous review semantics;
- accepted current Variant behavior remains unchanged.

## Controlled Sync regression

Verify:

- only current Missing+Wanted identities are ready downloads;
- Missing+Ignored creates no download;
- Needs Review/Not Analyzed remain blockers;
- `DIFFERENT_VERSION` never triggers automatic replacement;
- Apply requires explicit confirmation and delegates to Downloads;
- Sync does not start unrelated queued downloads;
- no local file is deleted, moved, renamed or retagged by Sync;
- no Yandex mutation/upload is introduced by v0.9.0.

## Automated commands

Run Python from the repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Then run Flutter from `ui\musicark_ui`:

```powershell
flutter pub get
flutter analyze
flutter test test/account_session_test.dart
flutter test test/account_control_test.dart
flutter test test/app_settings_test.dart
flutter test test/v0_9_shell_test.dart
flutter test
```

On a Windows development machine run the development application:

```powershell
flutter run -d windows
```

Release packaging/build/signing is not part of this v0.9.0 task.

Do not record any command or manual scenario as passed until it was actually executed against `agent/v0.9.0-ui-account-settings`.
