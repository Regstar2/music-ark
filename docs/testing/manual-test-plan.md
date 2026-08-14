# Manual Test Plan

## v0.3 Windows + real Yandex validation

Run from a clean checkout of `agent/v0.3-yandex-library` without deleting `.musicark/musicark.db`.

### Automated baseline

1. `python -m unittest discover -s tests -v`
2. `flutter pub get`
3. `flutter analyze`
4. `flutter test`

All must be green before release.

### Migration / startup

1. Start with an existing v0.2 database containing Liked cache.
2. Launch v0.3.
3. Confirm no database deletion/re-login is requested.
4. Confirm cached Likes appears before network refresh completes.
5. Confirm existing Liked content remains intact after migration.

### Real playlists

1. With a valid stored session, open `Плейлисты`.
2. Confirm the list matches the real Yandex account and shows title, track count, owner when available, external ID, and local update time.
3. Open at least two real playlists, including one with many tracks if available.
4. Confirm title/artist/album and original ordering match Yandex.
5. Confirm duration/availability display when supplied by provider data.
6. Search by title, artist, and album; test original/title/artist sorting.
7. Search playlist list by title and switch original/title order.

### Refresh behavior

1. Add/remove a Liked track in Yandex and refresh Liked.
2. Add/remove/reorder tracks in one playlist and refresh that playlist.
3. Create or delete a playlist in Yandex, then use `Обновить библиотеку`.
4. Confirm a remotely deleted playlist disappears locally.
5. Confirm full library refresh remains responsive and does not eagerly load every playlist body.

### Offline fallback

1. Open a playlist successfully once.
2. Close MusicArk and disconnect network.
3. Relaunch.
4. Confirm cached Likes and playlist list are visible.
5. Open the previously cached playlist and confirm its tracks remain visible.
6. Trigger refresh and confirm an error banner appears without replacing cached content.

### Credentials/logout

1. Confirm token is not present in SQLite, logs, process argv, Git diff, or generated docs.
2. Logout.
3. Confirm next launch shows login and cached Yandex collections are cleared.

Record any discrepancy before marking v0.3 complete.
