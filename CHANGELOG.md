# Changelog

All notable project changes are recorded here.

## Unreleased

### Changed

- Restarted the supported desktop MVP around one user flow: Yandex Music token sign-in and Liked tracks display.
- Added a dedicated `musicark.mvp_bridge` that does not persist the token and does not require SQLite for the MVP flow.
- Replaced the previous multi-tab Flutter dashboard with the focused sign-in and Liked tracks interface.
- Added repository/Python runtime discovery for debug and in-repository release runs.
- Reworked README documentation around reproducible setup, run, test, and Windows build commands.
- Made `musicark.core.MusicArkApp` a lazy package export so provider-first imports cannot create an order-dependent circular import.

### Added

- Python unit tests for the MVP bridge.
- Fresh-process regression coverage for `python -m musicark.mvp_bridge`, preventing the circular-import failure from being hidden by unittest import order.
- Flutter widget test for sign-in and Liked tracks rendering.
- MVP product, architecture, version, testing, and release documentation.
- Synchronized `README.md` and `README_EN.md`.
