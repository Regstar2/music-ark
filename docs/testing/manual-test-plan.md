# Manual Test Plan — MusicArk v0.8.2 integration baseline

Use Windows with a controlled copy of the existing MusicArk state. Do **not** delete/reset the real `.musicark\musicark.db`, credentials, user audio, matching/variant/coverage/download/sync history, or a user's only copy of a test track.

Current code version: `0.8.2`. Current schema target: `1.8.4`.

## Preconditions

- use a copy of an MP3 for every metadata-write scenario;
- keep at least one local filename-collision case available;
- have cached Yandex Likes/playlists and a valid Local Library root;
- keep representative Coverage states: Covered, Missing+Wanted, Missing+Unreviewed, Missing+Ignored, Needs Review/Conflict, Not Analyzed, and a covered unresolved Variant result;
- optionally keep one unrelated queued download to verify queue isolation.

## Migration from v0.8.1

1. Start from an existing v0.8.1 database at schema `1.8.1`.
2. Launch the integrated v0.8.2 code.
3. Confirm forward migration reaches `1.8.4` through `1.8.2`, `1.8.3`, and `1.8.4` without replacing the database.
4. Restart the application and confirm initialization is idempotent.
5. Confirm preservation of:
   - Yandex credential/session;
   - cached Likes;
   - cached playlists;
   - Local Library roots;
   - indexed local files;
   - Matching decisions/conflicts/manual links;
   - Variant results;
   - Coverage actions;
   - Download queue/history/settings;
   - Sync plan/history state.

## Local Metadata Editor

Use a **copy** of a test MP3.

1. Open Local Library.
2. Open Metadata Editor for the copied file.
3. Change title, artist and album.
4. Save.
5. Read the file again and confirm persisted values.
6. Confirm the MPEG audio stream is still valid and playable.
7. Confirm unknown/custom ID3 frames that were not edited still exist.
8. Replace artwork and verify read-back/thumbnail refresh.
9. Remove artwork and verify the result.
10. Edit the filename and save.
11. Confirm the rename remains in the same directory and the Local Library points to the new path.
12. Attempt a colliding filename and confirm the existing file is not overwritten.
13. Confirm only the edited file is reindexed and its SHA-256 is refreshed.

## Yandex search / Compare

1. Open Metadata Editor for a copied MP3.
2. Search using separate **Название песни** and **Исполнитель** fields.
3. Select a Yandex result and open Compare.
4. Confirm available metadata/artwork values can be selected independently.
5. Confirm an empty Yandex value does not silently erase a non-empty local value.
6. Confirm protected/signed provider media URLs, token, cookies and Authorization headers are not exposed in Flutter-visible data.

## Apply Metadata

Run:

```text
Yandex search
→ Compare
→ select fields
→ Apply Metadata
```

Verify:

- selected metadata/artwork/filename changes are written transactionally;
- the resulting MP3 is valid;
- Local Library reflects the new path/metadata;
- SHA-256 is refreshed for the edited file;
- targeted Matching refresh runs;
- no new user-confirmed Exact identity is created from similarity alone;
- existing trusted provenance is preserved, but new trusted provenance is not fabricated merely by Apply Metadata.

## Apply + Bind

Run:

```text
Yandex search
→ Compare
→ Apply + Bind
```

Verify:

- selected metadata is applied through the same transactional write path;
- the local/Yandex relation is persisted as `exact_id`;
- confidence is `1.0`;
- reason is `user_confirmed`;
- trusted MusicArk/Yandex provenance is written as implemented;
- a fresh Local Library index can use that trusted provenance as an exact candidate.

## Content labels

For both a local track and a cached Yandex identity, test set/change/remove of:

```text
ОРИГИНАЛ
ЦЕНЗУРА
```

Repeat from Matching detail where applicable.

Verify:

- Yandex provider data is not mutated;
- local audio tags are not rewritten automatically;
- Matching identity/confidence is unchanged;
- the label is reflected in the relevant UI after refresh/restart.

## Variant acceptance

For current analyzer results `ALTERED`, `DIFFERENT_VERSION`, and `UNCERTAIN`:

1. confirm the item is an unresolved Variant blocker;
2. choose **«Эта версия меня устраивает»**;
3. confirm the blocker is resolved for Coverage/Controlled Sync;
4. confirm the raw analyzer status is unchanged;
5. choose **«Отменить принятие»** and confirm the blocker returns;
6. accept again, then change/recompute analysis evidence or fingerprints;
7. confirm the old acceptance no longer resolves the new analysis.

## Yandex artwork / playback

1. Refresh a Yandex collection that contains artwork.
2. Confirm row artwork is shown when available and older snapshots without artwork fall back safely until refreshed.
3. Play an available Yandex track.
4. Confirm playback uses a local backend-prepared file rather than a provider media URL in Flutter.
5. Replay the same track and confirm cache reuse does not create a Local Library entry.
6. Test an unavailable-track state.
7. Open a playlist and play a playlist track.
8. Confirm `.musicark/playback/yandex` files do not appear in Local Library, Matching or Coverage.

## Narrow window

Resize the application below the normal Yandex workspace width.

Expected:

- the Yandex workspace keeps its approximately 920 px minimum layout and becomes horizontally scrollable;
- no `RenderFlex overflow`;
- no `ListTile` trailing-width assertion/crash;
- no unhandled render exception.

This is a safeguard test, not a responsive/mobile redesign test.

## Controlled Sync regression

Use a small controlled set approximating:

```text
3 Covered
3 Missing + Wanted
2 Missing + Unreviewed
1 Missing + Ignored
1 Conflict / Needs Review
1 Not Analyzed
1 Covered + Different Version
```

Verify:

- only current Missing+Wanted identities are ready downloads;
- Missing+Unreviewed remains a user-decision blocker;
- Missing+Ignored creates no download;
- Needs Review/Not Analyzed remain matching blockers;
- unresolved Variant results remain Variant review items;
- an accepted current Variant is no longer a blocker while its evidence is unchanged;
- `DIFFERENT_VERSION` never triggers automatic replacement;
- Apply requires explicit confirmation and delegates to the Downloads queue;
- Sync does not start unrelated queued downloads;
- repeated Apply does not create duplicate active tasks;
- no local file is deleted, moved, renamed or retagged by Sync;
- Yandex likes/playlists/uploads/replacements are not mutated.

## Regression

Recheck existing flows:

- Yandex login/cache;
- Local Library scan;
- Matching and manual decisions;
- Variant analysis;
- Missing/Coverage and wanted/ignored actions;
- direct Download;
- Wanted Downloads;
- Local Playback;
- Controlled Sync history/staleness/revalidation.

## Automated commands

Run Python from the repository root:

```powershell
python -m unittest tests.test_yandex_provider tests.test_yandex_library -v
python -m unittest tests.test_metadata_editor_v082 -v
python -m unittest tests.test_content_labels_v082 -v
python -m unittest tests.test_variant_acceptance_v082 -v
python -m unittest discover -s tests -p "test_*.py" -v
```

Then run Flutter from `ui\musicark_ui`:

```powershell
flutter pub get
flutter analyze
flutter test test/yandex_track_controls_test.dart
flutter test test/yandex_narrow_layout_test.dart
flutter test test/metadata_editor_test.dart
flutter test test/matching_variant_page_test.dart
flutter test
```

On a Windows development machine also run:

```powershell
flutter build windows
flutter run -d windows
```

Do not record any command or manual scenario as passed until it was actually executed against the integration branch.
