# Release Checklist — v0.4.0 Local Library

## Automated

- [ ] `python -m unittest discover -s tests -v` is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] schema initializes twice without error and reports `1.3.0`.
- [ ] migration test preserves existing Yandex Liked/playlist cache.

## Local Library behavior

- [ ] native Windows folder picker opens.
- [ ] one root can be added and persists across restart.
- [ ] duplicate root is rejected.
- [ ] overlapping parent/child root is rejected.
- [ ] nested supported files are found; unknown extensions are ignored.
- [ ] missing tags use safe UI fallbacks.
- [ ] corrupted/permission-error file does not abort the scan.
- [ ] repeated unchanged scan does not reread/update every file.
- [ ] new file increments `added`.
- [ ] changed size/mtime increments `updated`.
- [ ] deleted file increments `removed` after a complete traversal.
- [ ] removing a root removes only index records, never physical files.
- [ ] search/sort/details work with Cyrillic/Unicode paths.

## Yandex regression

- [ ] saved Yandex session still restores.
- [ ] Liked tracks still load/refresh.
- [ ] playlists list still loads.
- [ ] playlist tracks still open.
- [ ] local migration does not clear provider cache.
- [ ] OAuth token is not logged or stored in SQLite.

## Safety / secrets

- [ ] diff contains no token, credentials, personal music paths, or binary music fixtures.
- [ ] scanner contains no rename/move/delete/tag-write/transcode operations.
- [ ] `.musicark/musicark.db` is never required to be deleted for upgrade.

## Manual Windows validation

- [ ] validate with `C:\MusicArk-Test` or equivalent disposable folder.
- [ ] restart persistence confirmed.
- [ ] add/change/delete/rescan sequence confirmed.
- [ ] native picker and real filesystem behavior confirmed.

Do not mark real-user-library validation complete unless it was actually run on a Windows machine with real local files.
