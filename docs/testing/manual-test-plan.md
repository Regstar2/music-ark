# Manual Test Plan — MusicArk v0.9.1 Main Screen UI Polish

Use Windows with a controlled copy of the existing MusicArk state. Do **not** delete/reset the real `.musicark\musicark.db`, credentials, user audio, matching/variant/coverage/download/sync history, or a user's only copy of a test track.

Current code version: `0.9.1`. Current schema target: `1.8.4`.

v0.9.1 must not change Matching, Variant, Coverage, Download, Controlled Sync, Metadata Editor, provider authentication, ORIGINAL/CENSORED semantics or file-mutation safety.

## Preconditions

- keep a valid cached Yandex session when testing signed-in startup;
- keep a logged-out scenario available;
- have cached Yandex Likes and at least two playlists;
- have at least two albums explicitly marked as liked in Yandex Music;
- have at least one Yandex track with artwork and one without artwork;
- have at least one ORIGINAL/CENSORED label;
- if possible, include one unavailable Yandex track;
- keep representative Local Library / Matching / Variant / Coverage / Download / Sync state;
- use a **copy** of an MP3 for every Metadata Editor write scenario.

## Main shell

1. Start MusicArk signed in.
2. Confirm there is only one permanent application sidebar.
3. Confirm the old nested permanent Yandex sidebar is absent.
4. Confirm the global sidebar exposes Yandex Music, Local Library, Matching, Missing, Downloads and Sync.
5. Confirm Settings and Account remain at the bottom.
6. Confirm the MusicArk mark/title render correctly in Light and Dark themes.
7. Navigate through all global destinations and confirm each remains reachable.

## Yandex — Tracks

1. Open Yandex Music.
2. Confirm `Треки / Tracks`, `Плейлисты / Playlists` and `Альбомы / Albums` top-level navigation is visible.
3. Confirm Liked tracks open by default for the cached signed-in session.
4. Confirm header shows title, track count, human-readable update time and source.
5. Confirm the raw ISO timestamp is not the primary visible timestamp.
6. Confirm refresh remains available.
7. Confirm normal tracks do not display the technical word `available`.
8. Confirm artwork, title, artist, album and duration are readable.
9. Search by title, artist and album.
10. Test Yandex order, title sort, artist sort and `Недоступные сначала / Unavailable first`.

## Yandex — Playlists

1. Switch to Playlists.
2. Confirm the playlist index shows title and track count.
3. Search playlists.
4. Test original and title sort.
5. Open one playlist.
6. Confirm playlist contents replace the index in the main workspace rather than opening a permanent nested sidebar.
7. Confirm `Назад к плейлистам / Back to playlists` returns to the playlist index.
8. Confirm playlist track search and refresh continue to work.

## Yandex — liked albums

1. In Yandex Music, explicitly like two albums. They do not need to correspond to albums represented by the user's liked tracks.
2. Refresh MusicArk Yandex Library.
3. Open `Альбомы / Albums`.
4. Confirm the two explicitly liked albums are shown.
5. Confirm an album that only happens to contain a liked track but is **not** itself liked does not appear solely for that reason.
6. Confirm album cards show artwork, title, artist and provider track count when available.
7. Search by album and artist.
8. Open one album and confirm its full album track list is shown, not just tracks from `Мне нравится / Liked`.
9. Confirm `Назад к альбомам / Back to albums` returns to the liked-album index.
10. Disconnect the network after one successful refresh and reopen MusicArk. Confirm the cached liked-album index remains visible.
11. Reconnect, unlike one album in Yandex Music, refresh, and confirm it leaves the active MusicArk liked-album index.

The album feature is read-only toward Yandex Music. MusicArk must not like/unlike albums or mutate provider state.

## ORIGINAL / CENSORED regression

1. Confirm a labeled Yandex track displays a compact `ОРИГИНАЛ / ORIGINAL` or `ЦЕНЗУРА / CENSORED` chip.
2. Open the inline label menu.
3. Change ORIGINAL → CENSORED.
4. Confirm the chip updates.
5. Remove the label and confirm the chip disappears.
6. Open `Пометки версий / Version labels` from the toolbar.
7. Confirm the general Yandex label manager still loads cached tracks and can edit labels.
8. Restart the app and confirm persisted labels are still present.
9. Confirm label operations do not change Yandex provider metadata, Matching identity or confidence.

## Availability

For an ordinary available track:

- no `available` text is shown;
- Play works normally.

For an unavailable track:

- the row is visually de-emphasized;
- Play is disabled;
- the tooltip explains that the track is unavailable in Yandex Music;
- `Недоступные сначала / Unavailable first` moves the row before available tracks;
- no raw `unavailable` provider value is shown as normal UI text.

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
- title/album text uses ellipsis rather than pushing actions off screen;
- search/sort/version-label toolbar reflows cleanly;
- row actions remain reachable;
- labeled tracks do not overflow in compact rows;
- playlist and album navigation remain usable;
- global sidebar/account control remain usable.

## Theme

Test `System`, `Light`, `Dark` and inspect sidebar, Yandex Tracks/Playlists/Albums/detail, track rows, labels, Now Playing and legacy feature pages. Restart and confirm persistence.

## Language

Test `System`, `Russian`, `English`.

1. Switch language without restart.
2. Confirm tabs, back navigation, search/sort, unavailable-first, version labels, table headers, empty states and album UI change language.
3. Confirm provider data, track titles, artists, albums, filenames and technical IDs remain untranslated.
4. Restart and confirm persistence.
5. Use an unsupported system locale and confirm deterministic Russian fallback in the main app.

## Now Playing

1. Start Yandex playback.
2. Confirm Now Playing appears at the application level.
3. Confirm title/artist presentation, Play/Pause, position, progress, duration and close/stop remain available.
4. Resize the window and confirm the player does not overflow.
5. Navigate Yandex → Local → Settings → Help and confirm ordinary navigation does not destroy the active player.

## Account/session regression

1. Start from cached signed-in state and confirm account presentation is immediate/cache-first.
2. Disconnect network and confirm a failed refresh does not visually log the cached account out.
3. Logout through the global account menu and confirm both global account state and Yandex page become logged out.
4. Sign in again using the existing Yandex token flow.
5. Confirm no second credential store or duplicate account UI was introduced.

## v0.8.2/v0.9.0 behavior regression

Recheck:

```text
Scan     → read-only user audio
Matching → read-only user audio
Coverage → read-only user audio
Sync     → no user audio mutation
```

Also verify:

- Matching remains identity matching and does not absorb Variant semantics;
- Missing remains distinct from Different Version;
- `DIFFERENT_VERSION` never triggers automatic replacement;
- accepted Variant behavior is unchanged;
- Download queue semantics are unchanged;
- Controlled Sync still requires explicit confirmation and delegates acquisition to Downloads;
- Metadata Editor `Apply Metadata` remains distinct from `Apply + Bind`;
- no Yandex Upload/reverse Sync was introduced.

## Automated commands

From repository root:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

From `ui\musicark_ui`:

```powershell
flutter pub get
flutter analyze
flutter test test\widget_test.dart
flutter test test\feature_bridge_wiring_test.dart
flutter test test\v0_9_shell_test.dart
flutter test test\v0_9_1_content_labels_test.dart
flutter test test\v0_9_1_responsive_test.dart
flutter test test\v0_9_1_localization_test.dart
flutter test test\yandex_content_label_test.dart
flutter test test\yandex_track_controls_test.dart
flutter test test\yandex_narrow_layout_test.dart
flutter test
flutter run -d windows
```

Do not record any command or manual scenario as passed until it was actually executed against the final `agent/v0.9.1-main-ui-polish` head.
