# Manual Test Plan — MusicArk v0.9.7 Settings, Help & About UI Polish

Use Windows with a controlled copy of the existing MusicArk state. Do **not** delete/reset the real `.musicark\musicark.db`, credentials, user audio, matching/variant/coverage/download/sync history, or a user's only copy of a test track.

Current code version: `0.9.7`. Current schema target: `1.8.4`.

v0.9.7 must not change Matching, Variant, Coverage, Download, Controlled Sync, Metadata Editor, provider authentication, ORIGINAL/CENSORED semantics or file-mutation safety.

## Preconditions

- keep a valid cached Yandex session when testing signed-in startup;
- keep a logged-out scenario available;
- keep representative Local Library / Matching / Variant / Coverage / Download / Sync state;
- use a **copy** of an MP3 for every Metadata Editor write scenario;
- test both Russian and English utility strings;
- test Light and Dark themes;
- keep at least one long provider display name scenario if possible.

## v0.9.7 Settings

1. Open Settings on a wide desktop window.
2. Confirm the page content is centered/constrained rather than stretched edge to edge.
3. Confirm the header shows the page description and compact auto-save status.
4. Confirm there is no separate `General / Общие` card whose only purpose is the auto-save sentence.
5. Switch System → Light → Dark and confirm each change applies immediately.
6. Switch System → Russian → English and confirm each change applies immediately.
7. Restart and confirm theme/locale persistence.
8. Reduce the application window to around 900 px wide and confirm theme/language controls reflow below their descriptions without `RenderFlex overflow`.
9. In logged-out state confirm the provider card shows Yandex Music plus the existing Sign in action.
10. In signed-in state confirm the provider card shows the account display name, active-session state and Open Yandex Music action.
11. Confirm initials/generic icon fallback is used when no verified public avatar is available.
12. Confirm a long display name uses ellipsis and does not push the account action outside the card.
13. Confirm Help and About rows are clickable across the full row.

## v0.9.7 Help

1. Open Settings → Help.
2. Confirm the breadcrumb/back action clearly returns to Settings.
3. Confirm the intro card explains how the local help is organized.
4. Confirm the four groups are visible:
   - Library;
   - Collection analysis;
   - Recovery and actions;
   - Application.
5. Confirm all 11 topics exist:
   - Yandex Music;
   - Local Library;
   - Matching;
   - Track versions and censorship;
   - Missing;
   - Downloads;
   - Sync;
   - Metadata Editor;
   - Artwork and playback;
   - Settings;
   - Data safety.
6. Confirm each topic is closed by default and shows a short summary.
7. Expand every topic and confirm detailed text is readable in Russian.
8. Repeat in English and confirm no topic becomes substantially less informative.
9. Specifically verify Help states that:
   - Identity is not Metadata;
   - Identity is not Variant;
   - similarity/confidence alone is not confirmed identity;
   - Missing is not Different Version;
   - ORIGINAL/CENSORED does not modify Yandex or audio metadata;
   - Variant acceptance does not turn the analyzer result into SAME;
   - Sync is not a bidirectional filesystem mirror;
   - Metadata Editor is the explicit ordinary write boundary;
   - full safe writing is MP3/ID3-only in the current editor;
   - playback cache is not Local Library content.
10. Resize while one or more topics are expanded and confirm text wraps without horizontal overflow.
11. Return Help → Settings and confirm Now Playing/Yandex session state is preserved.

## v0.9.7 About

1. Open Settings → About.
2. Confirm the existing vector MusicArk mark, product name and `0.9.7` version are visible.
3. Confirm `Version and environment` shows application version, backend version, schema, OS, theme and language.
4. On a wide window confirm environment values use two columns.
5. On a narrow desktop window confirm the section becomes one column and important values wrap rather than disappear.
6. Use `Copy diagnostic information` and confirm the clipboard contains version/backend/schema/OS/theme/locale only.
7. Confirm diagnostics do **not** contain Yandex token, cookies, protected media URLs, local library file lists or collection contents.
8. Open standard dependency licenses and confirm Flutter license UI is reachable.
9. Confirm the GitHub repository URL is selectable and the copy-link action copies the repository URL.
10. Return About → Settings and confirm Now Playing/Yandex session state is preserved.

## Main shell regression

1. Confirm there is only one permanent application sidebar.
2. Confirm the global sidebar exposes Yandex Music, Local Library, Matching, Missing, Downloads and Sync.
3. Confirm Settings and Account remain at the bottom.
4. Confirm the MusicArk mark/title render correctly in Light and Dark themes.
5. Navigate through all global destinations and confirm each remains reachable.
6. Navigate Yandex → Settings → Help → Settings → About → Settings → Yandex and confirm the Yandex workspace is not reset by utility navigation.

## Yandex regression

1. Open Yandex Music and confirm `Tracks / Liked`, `Playlists` and `Albums` remain reachable.
2. Confirm refresh, search/sort, playlist detail/back and liked-album detail/back continue to work.
3. Confirm normal tracks do not display raw technical `available` text.
4. Confirm unavailable tracks remain visually de-emphasized and playback-disabled with the explanatory tooltip.
5. Confirm ORIGINAL/CENSORED editing remains available and does not mutate Yandex provider metadata, Matching identity or confidence.
6. Confirm Yandex playback still uses the application-wide Now Playing surface.

## Local / Matching / Coverage / Downloads / Sync regression

Recheck:

```text
Scan     → read-only user audio
Matching → read-only user audio
Coverage → read-only user audio
Sync     → no existing user-audio mutation
```

Also verify:

- Local Library root filtering does not change configured sources unless root-management actions are explicitly used;
- Matching remains identity matching and does not absorb Variant semantics;
- Missing remains distinct from Different Version;
- `DIFFERENT_VERSION` never triggers automatic replacement;
- accepted Variant behavior is unchanged;
- Download queue semantics and safe failed-task removal are unchanged;
- Controlled Sync still requires explicit confirmation and delegates acquisition to Downloads;
- Metadata Editor `Apply Metadata` remains distinct from `Apply + Bind`;
- no Yandex Upload/reverse Sync was introduced.

## Responsive desktop layout

Check at least:

```text
1920×1080
1600×900
1366×768
narrow desktop window around 900 px application width
```

At every width verify:

- no `RenderFlex overflow`;
- no ListTile/trailing assertion;
- utility-page controls reflow cleanly;
- Help text remains readable when expanded;
- About environment/actions remain reachable;
- global sidebar/account control remain usable;
- Now Playing remains usable.

## Theme

Test `System`, `Light`, `Dark` and inspect sidebar, Yandex, Local, Matching, Missing, Downloads, Sync, Settings, Help, About and Now Playing. Restart and confirm persistence.

## Language

Test `System`, `Russian`, `English`.

1. Switch language without restart.
2. Confirm Settings, all 11 Help topics, About sections/actions and existing primary workspaces change language.
3. Confirm provider data, track titles, artists, albums, filenames and technical IDs remain untranslated.
4. Restart and confirm persistence.
5. Use an unsupported system locale and confirm deterministic Russian fallback in the main app.

## Now Playing

1. Start Yandex or Local playback.
2. Confirm Now Playing appears at application level.
3. Navigate through Settings, Help and About and confirm ordinary utility navigation does not destroy the active player.
4. Resize the window and confirm the player does not overflow.

## Account/session regression

1. Start from cached signed-in state and confirm account presentation is immediate/cache-first.
2. Disconnect network and confirm a failed refresh does not visually log the cached account out.
3. Confirm Settings provider card reflects the same global session state.
4. Logout through the existing global account menu and confirm both global account state and Yandex page become logged out.
5. Sign in again using the existing Yandex token flow.
6. Confirm no second credential store or duplicate login flow was introduced.

## Automated commands

From repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

From `ui\musicark_ui`:

```powershell
flutter pub get
flutter analyze
flutter test test\utility_pages_test.dart
flutter test test\v0_9_shell_test.dart
flutter test
flutter run -d windows
```

Do not record any command or manual scenario as passed until it was actually executed against the final `agent/v0.9.7-settings-help-about-ui` head.
