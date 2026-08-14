# Manual Test Plan — MusicArk v0.5

Use the real cached Yandex Library together with a disposable/local test collection such as `C:\MusicArk-Test`. Do not delete `.musicark\musicark.db`, saved Yandex credentials, or music files for this test.

## Preconditions

- Windows Flutter desktop target works;
- v0.4 database/local roots are kept in place so migration `1.4.0` is exercised;
- Yandex Liked is loaded; open/refresh representative playlists so their tracks are cached;
- Local Library is scanned and includes structured metadata;
- fixture contains at least 10 obvious matches, 5 harder matches, live/remix/acoustic variants, and same-title/different-artist examples where possible.

## Migration / regression baseline

1. Launch v0.5 against the existing v0.4 database.
2. Confirm Yandex saved session, Liked, playlists, and cached playlist tracks remain available.
3. Confirm Local Library roots/tracks/search/sorting remain available.
4. Do not rescan only to make migration work; `initialize_database()` must upgrade automatically.

## Matching baseline

1. Open **Сопоставление**.
2. Confirm Yandex and Local track counts are plausible.
3. Click **Запустить сопоставление**.
4. Confirm final counts are shown for matched / conflicts / unmatched.
5. Open filters **Все**, **Совпало**, **Требует проверки**, **Не найдено**.
6. Search by Yandex title/artist and local title/artist/path.
7. Check sorting by confidence, artist, title, and status.

## Precision review

Inspect at least:

- 10 obvious title+artist matches with close duration;
- 5 difficult matches with edition/album differences;
- several `Live`, `Remix`, `Acoustic`, `Instrumental`, or `Remaster` cases;
- same-title tracks from different artists;
- multi-artist / `feat.` cases;
- FLAC+MP3 duplicates where both are plausible.

Expected policy: false positives are unacceptable. A doubtful case should be `CONFLICT` or `UNMATCHED`, not `MATCHED`.

## Conflict review / manual decisions

1. Open one conflict.
2. Compare Yandex and local title, artists, album, duration, path, and confidence.
3. Confirm multiple top candidates are shown when available.
4. Accept the correct candidate.
5. Restart MusicArk.
6. Confirm the result is still matched manually.
7. Pick another conflict and reject its best wrong candidate.
8. Run matching again.
9. Confirm the rejected candidate does not return as the same active best candidate.
10. If another candidate remains, verify it can be accepted instead.

## Incremental behavior

- Run matching twice without Yandex/Local changes: the second run should report unchanged work instead of needlessly recomputing everything.
- Change metadata of a test local file externally, rescan Local Library, then rerun matching; affected automatic result should be eligible for recalculation.
- Delete a test local file externally, rescan, then rerun; a link to the removed file must not remain valid.
- Refresh Yandex metadata/library, then rerun; changed provider metadata must be eligible for recalculation.
- A manual accepted link must not be overwritten by an ordinary automatic rerun.

## Duplicate collection identity

Use a Yandex track that appears in Liked and at least one playlist. Matching must show/process it as one provider identity, not one result per collection occurrence.

## Offline / privacy

After Yandex cache and Local Library are populated:

1. disconnect network access;
2. launch the app;
3. run matching;
4. review results and manual decisions.

Matching should continue to work because it is local-only. No local metadata should be sent to Yandex or third-party matching/metadata services.

## Safety regression

During all matching tests verify MusicArk does not:

- rename, move, delete, transcode, or edit tags/artwork of local audio files;
- like/dislike tracks, edit playlists, upload, or otherwise mutate Yandex Music;
- remove stored Yandex credentials;
- delete `.musicark\musicark.db`.

## Automated commands

```powershell
python -m unittest discover -s tests -v
cd ui\musicark_ui
flutter analyze
flutter test
```

## Pass criteria

- migration `1.3.0 → 1.4.0` preserves v0.4 Yandex/Local data;
- no Cartesian-product behavior is observed in the implementation/scale regression;
- obvious auto-matches are correct and ambiguous cases are conservative;
- manual accept/reject persists across restart/rerun;
- rejected candidates do not immediately return as active best candidates;
- deleted local files invalidate links;
- Yandex and Local Library regressions remain working;
- Python tests, Flutter analyzer, and Flutter tests are green on Windows;
- real-library precision is reviewed before the version is considered accepted.
