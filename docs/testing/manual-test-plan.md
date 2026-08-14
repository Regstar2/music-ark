# Manual Test Plan — MusicArk v0.4

Use a disposable folder such as `C:\MusicArk-Test`. Do not use the primary personal collection for the first smoke test.

## Preconditions

- Windows desktop target is available in Flutter;
- existing `.musicark\musicark.db` is kept in place;
- an existing saved Yandex token, if present, is not deleted;
- `C:\MusicArk-Test` contains a few small audio files, including at least one tagged file and one file without useful title/artist tags.

## Local Library baseline

1. Launch MusicArk.
2. Open **Локальная библиотека**.
3. Click **Добавить папку** and select `C:\MusicArk-Test` through the native folder dialog.
4. Confirm the root is listed.
5. Click **Сканировать**.
6. Confirm tracks appear with title/artist/album/duration where available.
7. Open one track and verify path, format, bitrate/sample rate when available.
8. Close the app and launch it again.
9. Confirm the root and indexed tracks are still present before another scan.

## Incremental reconciliation

1. Add one supported audio file to `C:\MusicArk-Test`.
2. Rescan; expected: `added +1`.
3. Modify one existing audio file/tag using an external tool.
4. Rescan; expected: `updated +1` if file size or mtime changed.
5. Delete one test audio file outside MusicArk.
6. Rescan; expected: `removed +1` and the row disappears from Local Library.
7. Rescan again without changes; expected: existing rows are `unchanged` and no duplicates appear.

## Error resilience

- add or create a corrupted file with a supported extension; scan must finish and report an error instead of aborting the whole library;
- include Unicode/cyrillic names, spaces, and nested folders;
- verify unknown extensions are ignored;
- if feasible, include a directory symlink/junction and confirm the scanner does not recursively follow it.

## Root management

- add a second independent root and scan it;
- attempt to add the same root using case/trailing-separator variation: it must be rejected;
- attempt to add a child of an already indexed root: overlapping roots must be rejected;
- remove a root in MusicArk and confirm the dialog says only index data is removed;
- verify the actual music files still exist on disk after root removal.

## Search / sorting / large-list contract

- search by title, artist, album, and filename;
- sort by artist, title, album, duration, and path;
- on a sufficiently large fixture, confirm additional pages can be loaded without passing the full library through one fixed-size bridge payload.

## Yandex regression

After the local tests:

1. open **Яндекс Музыка**;
2. confirm saved session restore still works;
3. open **Мне нравится**;
4. open playlist list and one playlist;
5. refresh Yandex library;
6. restart and verify cached Yandex data remains available.

## Pass criteria

- no local audio file is modified by MusicArk;
- no Yandex cache is destroyed by migration `1.3.0`;
- roots/tracks persist across restart;
- new / updated / removed / unchanged counts match filesystem changes;
- Python suite, `flutter analyze`, and `flutter test` are green on the user's Windows environment.
