# Manual Test Plan — MusicArk v0.7.0 Download

Use Windows and the real cached Yandex Library together with the real Local Library. Begin with **1–3 tracks**, never with the full wanted set. Do not delete `.musicark\musicark.db`, the saved Yandex credential, existing Local Library files, matching/manual decisions, Variant results, or Coverage actions.

## Preconditions

- Windows Flutter desktop target works;
- existing v0.6 database is available so `1.6.0 → 1.7.0` migration is exercised;
- Yandex session/token works through the normal secure credential flow;
- Yandex Liked/playlists are loaded;
- one or more Local Library roots are configured and scanned;
- Matching has run and there are representative `MATCHED`, `CONFLICT`, `UNMATCHED`, and preferably `not_analyzed` states;
- several proven Missing rows are available;
- enough free disk space exists in the selected test folder.

## Migration / regression

1. Launch v0.7 against the existing v0.6 database.
2. Confirm schema becomes `1.7.0` automatically.
3. Restart once and confirm repeated initialization is harmless.
4. Confirm Yandex session/cache/Liked/playlists remain present.
5. Confirm Local Library roots and existing indexed tracks remain present.
6. Confirm Matching results, manual accept/reject, conflicts, Variant results, and wanted/ignored decisions remain present.
7. Confirm legacy download/reference rows remain in storage but are **not shown in the user Downloads page**.
8. Confirm no DB reset or manual SQL is required.

## Primary 1–3 track scenario — one click

For one proven `missing` track that is currently `unreviewed`:

```text
1. open Недостающие
2. find a Missing track
3. do NOT press Нужен first
4. press Скачать once
5. if no target exists, choose the test download folder
6. download starts without manually opening/starting the queue
7. observe final success/error message
8. open Загрузки only to inspect progress/history
9. verify physical final file exists in the exact selected folder
10. verify no .part remains
11. open Local Library and find the file
12. verify local_audio_files.library_root_id is non-NULL
13. verify normalized_path/metadata are populated
14. refresh Missing/Coverage
15. track is covered and disappears from default Missing
16. restart MusicArk
17. completed user task history remains visible
```

Also confirm the single click internally changed the historical action to `wanted`; this is an implementation invariant, not a required separate user interaction.

Repeat for at most 1–2 additional tracks before any batch test.

## Exact destination persistence

This specifically covers the reported “folder changes after leaving Downloads” regression:

1. Open `Загрузки`.
2. Select a distinctive disposable folder, for example `C:\MusicArkTest\ChosenHere`.
3. Record exactly what the UI shows as the target.
4. Switch to `Недостающие`, `Локальная библиотека`, and another tab.
5. Return to `Загрузки`.
6. Confirm the target is still the **same exact path**, not a parent Local Library root and not a newly derived `<root>\MusicArk` path.
7. Restart MusicArk and confirm the exact selected path remains.
8. Download one track and confirm its file is written directly into the selected folder.

If the selected directory is inside an existing Local Library root, the parent root may remain the indexing owner internally, but the visible/download target must remain the exact selected directory.

For a database created before exact `target_path` persistence, re-select the folder once. Thereafter it must remain stable.

## Filename / path safety

- with no target configured, pressing `Скачать` must route the user to choose a folder rather than silently using `.musicark`;
- changing the default target affects newly enqueued tasks, not target snapshots already stored in queued tasks;
- filenames contain the stable Yandex ID and remain valid with Cyrillic, spaces and Unicode;
- titles/artists containing `< > : " / \\ | ? *`, trailing dots/spaces, or Windows reserved names cannot escape/create invalid paths;
- reference cache `.musicark\downloads\yandex\` is not used as the user destination and is not shown as user history.

## Eligibility

Backend truth table remains:

```text
missing + wanted    → allowed
missing + ignored   → direct Скачать first changes action to wanted, then allowed
missing + unreviewed→ direct Скачать first changes action to wanted, then allowed
covered + wanted    → rejected/skipped
conflict + wanted   → rejected
not_analyzed+wanted → rejected
MATCHED + DIFFERENT_VERSION → not downloaded by default
```

A track present in Liked + several playlists still creates one active user download task.

## Queue / legacy isolation

- queued/running/completed/failed/cancelled/skipped states display correctly;
- filters All / queued / running / completed / errors work;
- repeated enqueue of the same active provider identity does not duplicate tasks;
- completed tasks are not rerun;
- `Скачать все «Нужные»` starts the user queue automatically;
- `Продолжить очередь` remains a recovery/manual control, not a required ordinary step;
- clearing completed history removes only v0.7 user task history and never audio files;
- internal/legacy reference-download rows are not shown, run, cancelled, retried, recovered, or cleared by the v0.7 user queue UI;
- restart preserves user completed/failed/queued/cancelled history.

## File actions / path privacy

For a completed download and an ordinary Local Library track:

- the full filesystem path is **not printed by default** on the row/card;
- `Показать путь` reveals the full path only on request;
- `Скрыть путь` hides it again where applicable;
- `▶ / Воспроизвести` opens the local file using the Windows default associated audio player;
- `Открыть расположение файла` opens Explorer and selects/reveals the real file;
- a missing/deleted physical file produces an error instead of launching an unrelated path.

This v0.7 check is for system-player launch only. An embedded MusicArk play/pause/seek player is not part of this release.

## Crash recovery

1. Start a user download.
2. Terminate MusicArk during `running` (use a disposable test track/location).
3. Relaunch.
4. Confirm the user task does not remain permanently `running`.
5. Expected behavior: `failed` with an interrupted reason and Retry available.
6. Confirm any matching `.part` was removed.
7. Confirm internal/reference tasks were not changed by user-download recovery.
8. Retry and confirm exactly one final indexed file exists.

## Progress

For a normal response with known size:

- downloaded bytes increase;
- total bytes are shown;
- percentage reflects actual bytes;
- UI remains responsive.

For unknown length, if a controlled mock/debug path is available:

- progress is indeterminate;
- no fake 10%/90% values appear.

## Cancellation

For a running user track:

```text
start
→ Cancel
→ streaming stops cooperatively
→ .part removed
→ final corrupted file absent
→ task = cancelled
→ Coverage remains missing
```

For a queued user task, Cancel should be immediate. No arbitrary PID/process kill should occur.

## Failure scenarios

### Network off

- press `Скачать` for a Missing track with network unavailable;
- app remains running;
- task becomes failed with a network-class error;
- queue persists;
- track stays Missing + wanted;
- Retry remains available.

### Authentication failure

- use an expired/invalid saved Yandex token through the normal auth test path;
- queue is not deleted;
- UI reports that Yandex Music re-authorization is required;
- no token appears in logs/task detail/SQLite.

### Unavailable track / no download info

- task becomes failed/unavailable rather than silently trying YouTube/VK/torrents/web search;
- track remains Missing;
- no third-party fallback occurs.

## Post-download product gate

For every reported `completed` user task verify all are true:

- final file exists and size > 0;
- audio metadata reader can open it;
- Local Library lists it;
- `library_root_id` is non-NULL;
- exact provider/local link exists with method `exact_id`;
- Coverage returns `covered`;
- no new Variant row was fabricated merely because the download was exact.

A task must not be treated as successful if indexing/linking/coverage refresh failed after HTTP completion.

## Existing destination / Retry

- retry after a transient failure must not create duplicate final files;
- a valid existing file for the same stable Yandex identity may be reused/indexed safely;
- MusicArk must not overwrite arbitrary unrelated existing music;
- corrupted/partial `.part` files must never appear as valid Local Library tracks.

## Batch scenario

Only after the 1–3 track checks pass:

```text
5–10 Missing tracks marked Нужен
→ Скачать все «Нужные»
→ queue starts automatically
```

Verify:

- one task per provider identity;
- no duplicate files;
- queue runs with bounded concurrency (baseline v0.7 is sequential);
- Flutter stays responsive;
- binary data is not buffered into SQLite/Flutter;
- Local Library is not fully rescanned after every completed file;
- each completed file becomes Covered independently.

## v0.4–v0.6 regression

Confirm after v0.7:

- Yandex Library / playlists still work;
- Local Library existing files are not renamed/moved/deleted/tag-edited;
- v0.5 Matching retains MATCHED/CONFLICT/UNMATCHED semantics and manual precedence;
- v0.5.1 Variant remains independent, including `DIFFERENT_VERSION` staying Covered;
- v0.6 Coverage truth table remains correct;
- wanted/ignored triage persists;
- strict reference cache still does not count as Local Library coverage.

## Privacy / repository safety

During testing verify:

- token is absent from argv, queue DB, raw payload, logs, filename, audit detail and UI;
- temporary direct URLs are not persisted or displayed;
- Local Library data is not uploaded beyond the minimum selected Yandex provider request;
- real downloaded `.mp3/.flac/.m4a/...` files are never staged/committed to Git;
- `.musicark\musicark.db` and the saved credential are never deleted by setup/test instructions.

## Automated commands

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

## Pass criteria

- migration remains forward-only/idempotent and preserves existing state;
- exact selected target survives tab/service recreation and restart;
- one-click `Missing -> Скачать` works without a prior manual `Нужен` click;
- user queue is isolated from internal/reference queue history/actions;
- progress/cancellation/retry/crash recovery behave as documented;
- successful downloads become normal Local Library rows with non-NULL root IDs;
- exact identity link is created without fuzzy matching or fabricated Variant state;
- successful downloaded tracks become Covered automatically;
- path is hidden by default and play/reveal file actions work on Windows;
- 5–10 track batch has no duplicate tasks/files or full rescan-per-file behavior;
- Python tests, Flutter analyzer and Flutter tests are green;
- the real Windows 1–3 track validation above is completed before release acceptance.

Do not claim real Yandex download, Windows UI, or full release validation until these checks have actually run.
