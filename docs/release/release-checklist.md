# Release Checklist

## v0.3.0

- [ ] Branch is based on the latest `agent/v0.2-persistent-library` state.
- [ ] `git diff` contains no token, credentials, `.env`, or local secrets.
- [ ] Existing `.musicark/musicark.db` upgrades automatically to schema `1.2.0`.
- [ ] Existing v0.2 Liked snapshot survives migration.
- [ ] Full Python test suite is green.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] Windows app launches from the documented environment.
- [ ] Stored Yandex session restores without token input.
- [ ] Real Yandex playlist list is visible.
- [ ] A real playlist opens and displays its real ordered tracks.
- [ ] Liked and playlist refresh work.
- [ ] Deleted remote playlist disappears after full library refresh.
- [ ] Offline restart shows cached library and previously cached playlist tracks.
- [ ] Network refresh error leaves cached data visible.
- [ ] Logout clears credential and Yandex cache.
- [ ] Python/Flutter/docs versions are `0.3.0`.
- [ ] README RU/EN describe the same feature set.
- [ ] Draft PR documents which real Windows/Yandex checks are still pending.

Do not mark the release validated only from mocked/unit tests.
