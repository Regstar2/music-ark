# Manual Test Plan — MusicArk v0.7.0 Download

Use Windows and the real cached Yandex Library together with the real Local Library. Begin with **1–3 tracks**, never with the full wanted set. Do not delete `.musicark\musicark.db`, the saved Yandex credential, existing Local Library files, matching/manual decisions, Variant results, or Coverage actions.

## Preconditions

- Windows Flutter desktop target works;
- existing v0.6 database is available so `1.6.0 → 1.7.0` migration is exercised;
- Yandex session/token works through the normal secure credential flow;
- Yandex Liked/playlists are loaded;
- one or more Local Library roots are configured and scanned;
- Matching has run and there are representative `MATCHED`, `CONFLICT`, `UNMATCHED`, and preferably `not_analyzed` states;
- several proven Missing rows can safely be marked `wanted`;
- enough free disk space exists in the selected test root.

## Migration / regression

1. Launch v0.7 against the existing v0.6 database.
2. Confirm schema becomes `1.7.0` automatically.
3. Restart once and confirm repeated initialization is harmless.
4. Confirm Yandex session/cache/Liked/playlists remain present.
5. Confirm Local Library roots and existing indexed tracks remain present.
6. Confirm Matching results, manual accept/reject, conflicts, Variant results, and wanted/ignored decisions remain present.
7. Confirm legacy download-task rows remain readable.
8. Confirm no DB reset or manual SQL is required.

## Primary 1–3 track scenario

For one proven `missing` track:

```text
1. Yandex Library loaded
2. Local Library scanned
3. Matching run
4. open Недостающие
5. mark track Нужен
6. press В загрузки
7. if needed choose a Local Library root/folder
8. open Загрузки
9. press Запустить очередь
10. observe real/indeterminate progress
11. wait for completed
12. verify physical final file exists
13. verify no .part remains
14. open Local Library and find the file
15. verify local_audio_files.library_root_id is non-NULL
16. verify normalized_path/metadata are populated
17. refresh Missing/Coverage
18. track is covered and disappears from default Missing
19. restart MusicArk
20. completed task history remains visible
```

Repeat for at most 1–2 additional tracks before any batch test.

## Destination / filename

- with no target configured, enqueue/run workflow must ask the user to choose a folder rather than silently using `.musicark`;
- selecting a new folder makes it a valid Local Library root;
- selecting a folder under an existing root keeps downloads inside that root's managed `MusicArk` location;
- restart preserves the selected default root;
- changing the default target affects newly enqueued tasks, not target snapshots already stored in queued tasks;
- filenames contain the stable Yandex ID and remain valid with Cyrillic, spaces and Unicode;
- titles/artists containing `< > : " / \\ | ? *`, trailing dots/spaces, or Windows reserved names cannot escape/create invalid paths;
- reference cache `.musicark\downloads\yandex\` is not used as the user download destination.

## Eligibility

Verify the ordinary enqueue rule exactly:

```text
missing + wanted    → allowed
missing + ignored   → rejected / not included in bulk
missing + unreviewed→ rejected / not included in bulk
covered + wanted    → rejected/skipped
conflict + wanted   → rejected
not_analyzed+wanted → rejected
MATCHED + DIFFERENT_VERSION → not downloaded by default
```

A track present in Liked + several playlists still creates one active download task.

## Queue / persistence

- queued/running/completed/failed/cancelled/skipped states display correctly;
- filters All / queued / running / completed / errors work;
- repeated enqueue of the same active provider identity does not duplicate tasks;
- completed tasks are not rerun by ordinary Run queue;
- clearing completed history removes only SQLite task history and never the audio file;
- restart preserves completed/failed/queued/cancelled history.

## Crash recovery

1. Start a download.
2. Terminate MusicArk during `running` (use a disposable test track/location).
3. Relaunch.
4. Confirm the task does not remain permanently `running`.
5. Expected v0.7 behavior: it is `failed` with an interrupted reason and Retry is available.
6. Retry from zero and confirm exactly one final indexed file exists.

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

For a running track:

```text
start
→ Cancel
→ streaming stops cooperatively
→ .part removed
→ final corrupted file absent
→ task = cancelled
→ Coverage remains missing
```

For a queued task, Cancel should be immediate. No arbitrary PID/process kill should occur.

## Failure scenarios

### Network off

- start/attempt a wanted download with network unavailable;
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

For every reported `completed` task verify all are true:

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
- a valid existing managed file for the same stable Yandex identity may be reused/indexed safely;
- MusicArk must not overwrite arbitrary unrelated existing music;
- corrupted/partial `.part` files must never appear as valid Local Library tracks.

## Batch scenario

Only after the 1–3 track checks pass:

```text
5–10 missing+wanted tracks
→ Добавить все «Нужные»
→ Run queue
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

- `1.6.0 → 1.7.0` migration is forward-only/idempotent and preserves existing state;
- eligibility/dedup/recheck rules are correct;
- real progress/cancellation/retry/crash recovery behave as documented;
- successful downloads become normal Local Library rows with non-NULL root IDs;
- exact identity link is created without fuzzy matching or fabricated Variant state;
- successful downloaded tracks become Covered automatically;
- failure leaves technical Missing state intact;
- 5–10 track batch has no duplicate tasks/files or full rescan-per-file behavior;
- Python tests, Flutter analyzer and Flutter tests are green;
- the real Windows 1–3 track validation above is completed before release acceptance.

Do not claim real Yandex download, Windows UI, or full release validation until these checks have actually run.
