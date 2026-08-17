# Release Checklist — v0.8.2 integration baseline

This checklist is the acceptance gate for the v0.8.2 mainline candidate. It does not imply a published release or tag.

## Version / schema / Git

- [ ] Python package version is `0.8.2`.
- [ ] Flutter version is `0.8.2+1` unless an intentional build-number-only change is documented.
- [ ] SQLite forward migration reaches `1.8.4`.
- [ ] existing databases are migrated in place; no `.musicark/musicark.db` reset is required.
- [ ] repeated initialization is idempotent.
- [ ] integration branch is based on current `main` and preserves v0.8.1 + v0.8.2 history/functionality.
- [ ] final diff contains no unrelated generated/build files or secrets.
- [ ] README.md, README_EN.md, CHANGELOG and version docs describe the same baseline.

## Python automated checks

From repository root:

- [ ] `python -m unittest tests.test_yandex_provider tests.test_yandex_library -v`.
- [ ] `python -m unittest tests.test_metadata_editor_v082 -v`.
- [ ] `python -m unittest tests.test_content_labels_v082 -v`.
- [ ] `python -m unittest tests.test_variant_acceptance_v082 -v`.
- [ ] `python -m unittest discover -s tests -p "test_*.py" -v`.

If module names change, record the actual equivalent commands rather than claiming the listed commands passed.

## Flutter automated checks

From `ui/musicark_ui`:

- [ ] `flutter pub get`.
- [ ] `flutter analyze` with no accepted analyzer errors/warnings hidden by rule removal.
- [ ] `flutter test test/yandex_track_controls_test.dart`.
- [ ] `flutter test test/yandex_narrow_layout_test.dart`.
- [ ] `flutter test test/metadata_editor_test.dart`.
- [ ] `flutter test test/matching_variant_page_test.dart`.
- [ ] full `flutter test`.

## Migration / persistence

- [ ] realistic `1.8.1 → 1.8.4` migration preserves Yandex credential/session.
- [ ] cached Likes and playlists remain.
- [ ] Local Library roots and indexed files remain.
- [ ] Matching decisions/conflicts/manual links remain.
- [ ] Variant results remain.
- [ ] Coverage actions remain.
- [ ] Download queue/history/settings remain.
- [ ] Sync state/history remains.
- [ ] restart does not re-run a destructive migration.

## Metadata Editor

Using a copied test MP3:

- [ ] structured fields can be edited and read back.
- [ ] unknown/custom ID3 frames survive unrelated edits.
- [ ] artwork replacement/removal works.
- [ ] filename changes remain same-directory and refresh the index.
- [ ] filename collision never overwrites an existing file.
- [ ] audio stream remains valid after metadata writes.
- [ ] only the edited file is reindexed/rehashed.

## Apply Metadata / Apply + Bind

- [ ] Yandex search exposes separate title and artist inputs.
- [ ] Compare supports selective non-empty metadata/artwork import.
- [ ] Apply Metadata writes transactionally and refreshes Local/Matching state.
- [ ] Apply Metadata alone does not create user-confirmed Exact identity from similarity.
- [ ] Apply + Bind creates `exact_id`, confidence `1.0`, reason `user_confirmed`.
- [ ] trusted provenance is added only when the explicit bind contract requires it.
- [ ] reserved provenance tags are protected from normal Advanced Tags editing.

## Content labels

- [ ] local ORIGINAL/CENSORED set/change/remove works.
- [ ] cached Yandex ORIGINAL/CENSORED set/change/remove works.
- [ ] Matching detail can manage both subjects independently.
- [ ] labels do not mutate Yandex provider data.
- [ ] labels do not automatically rewrite audio metadata.
- [ ] labels do not alter Matching identity/confidence.

## Variant acceptance

For `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`:

- [ ] **Эта версия меня устраивает** resolves the actionable blocker.
- [ ] raw analyzer status remains unchanged.
- [ ] **Отменить принятие** restores the blocker.
- [ ] changed analysis evidence/fingerprint invalidates the old acceptance.

## Yandex Library / playback

- [ ] Yandex artwork renders when available.
- [ ] old snapshots without artwork fail safely to placeholder until refresh.
- [ ] first Yandex playback works.
- [ ] repeated playback can reuse private cache.
- [ ] unavailable-track state is handled.
- [ ] playlist-track playback works.
- [ ] Flutter receives only a local cache path, not token/auth/protected media URLs.
- [ ] playback cache is absent from Local Library, Matching and Coverage.

## Narrow-window safeguard

- [ ] Yandex workspace keeps an approximately 920 px minimum width.
- [ ] narrower outer windows scroll horizontally.
- [ ] no `RenderFlex overflow`.
- [ ] no `ListTile` trailing-width assertion/crash.
- [ ] no unhandled render exception.

## Controlled Sync / download regression

- [ ] Covered creates no acquisition.
- [ ] Missing+Wanted creates `ENQUEUE_DOWNLOAD` only.
- [ ] Missing+Unreviewed remains a decision blocker.
- [ ] Missing+Ignored creates no download.
- [ ] Needs Review / Not Analyzed remain matching blockers.
- [ ] unresolved Variant results remain review blockers.
- [ ] a valid accepted current Variant is not an unresolved blocker.
- [ ] `DIFFERENT_VERSION` never triggers automatic replacement.
- [ ] Apply requires explicit confirmation.
- [ ] Apply delegates to `DownloadService.enqueue()`.
- [ ] Apply never drains unrelated queue entries.
- [ ] active queued/running identity is not duplicated.
- [ ] v0.8.1 rich Yandex metadata/provenance download path is preserved.

## Safety invariants

In ordinary Scan/Matching/Coverage/Sync scenarios:

```text
modified existing user audio files = 0
Yandex provider mutations = 0
```

- [ ] existing user audio modification occurs only through an explicit Metadata Editor action.
- [ ] destructive tests use temporary files/copies, never the user's only original.
- [ ] no Yandex token, credentials, cookies, Authorization headers or protected/signed media URLs are committed/logged/persisted in unsafe locations.
- [ ] no real `.musicark` DB, music collection, `.env`, build outputs or private configs are committed.

## Windows build / manual acceptance

- [ ] `flutter build windows` succeeds on Windows.
- [ ] application is launched from the resulting Windows build or via the documented Windows run path.
- [ ] every applicable scenario in `docs/testing/manual-test-plan.md` is completed.

If the environment is not Windows or the toolchain is unavailable, record these gates as **NOT VERIFIED**, not passed.

## CI / PR

- [ ] Draft PR targets `main` from `agent/v0.8.2-mainline-integration`.
- [ ] GitHub Actions result is recorded as PASS / FAIL / BLOCKED / NOT STARTED.
- [ ] infrastructure/billing blockers are described as infrastructure blockers, not code-test failures.
- [ ] the PR remains Draft while required manual Windows acceptance is incomplete.
- [ ] the PR is not merged automatically.
