# Manual Test Plan — MusicArk v0.8.0 Controlled Sync

Use Windows with the existing `.musicark\musicark.db`, saved Yandex credential, cached Yandex library and real Local Library. Do **not** reset/delete the database, credentials, local audio, matching/variant/coverage/download/sync history.

## Preconditions

Prepare a controlled dataset approximating:

```text
3 Covered
3 Missing + Wanted
2 Missing + Unreviewed
1 Missing + Ignored
1 Conflict / Needs Review
1 Not Analyzed
1 Covered + Different Version
```

Have one valid Local Library download target and optionally one unrelated queued user download.

## Migration

1. Start from schema 1.7.0.
2. Launch v0.8 and confirm automatic schema 1.8.0.
3. Restart; initialization must be idempotent.
4. Confirm Yandex cache/session, Local roots/files, matching/manual/conflicts, Variant, wanted/ignored, Downloads/settings and legacy Sync history remain.
5. Open an old legacy sync plan if present; it may be viewed but must be marked unsupported and cannot Apply.

## Create / preview

1. Open **Синхронизация**.
2. Select `Мне нравится` (repeat later for all and one playlist).
3. Create plan.
4. Expected: exactly the 3 Missing+Wanted tracks are **ready to download**.
5. Missing+Unreviewed is shown under decision blockers.
6. Missing+Ignored is counted separately and is not a download.
7. Conflict and Not Analyzed are review/matching blockers.
8. Covered+Different Version is a Variant review item and never a replacement download.
9. Before Apply, verify no audio file appears and no new download task is created.
10. Current and Projected coverage must be visually distinct; projected counts only planned downloads hypothetically succeeding.

## Apply

1. Press **Применить**.
2. Verify explicit confirmation names the download count and states that existing local files are not changed/deleted.
3. Confirm.
4. Exactly the 3 Missing+Wanted identities are enqueued through the user Downloads queue.
5. Downloads do not auto-start from Sync.
6. Existing unrelated queued tasks are not started, cancelled, reprioritized or modified.
7. Repeating Apply does not create duplicate active tasks.
8. Use **Открыть Загрузки** to execute/inspect them through the existing v0.7 workflow.

## Complete one regression

Download exactly one planned track through v0.7. Rebuild the Sync Plan:

```text
A completed → Covered → absent from new download operations
B/C still Missing+Wanted → remain ready downloads
```

This is the controlled fingerprint-rebase regression gate.

## Staleness

For each case create a fresh plan first, then change exactly one input and return to Sync:

- wanted → ignored;
- active Yandex membership changes after cache refresh;
- Local Library scan/index changes local state;
- Matching result changes;
- download target changes.

Expected: plan becomes **stale**, Apply disabled/refused, and UI asks to create a new plan.

Playback start/position/queue changes must **not** make a plan stale.

## Race revalidation

After a valid plan has passed preview, make one planned identity Covered before enqueue (controlled debug/test timing). Apply must record it as skipped/already covered and must not create a duplicate download.

## Scope semantics

- all: same provider identity in Liked + Playlist A + Playlist B is one desired track;
- liked: only Liked membership;
- playlist A/B: only identities in that selected active Yandex Playlist;
- duplicate occurrences inside a playlist create one download candidate;
- a local track outside a selected playlist is labelled **Outside this scope**, never “delete”.

## No target

Plan generation/preview must work without a download target. Apply must remain disabled/refused. Selecting a target after the plan should make that old plan stale; rebuild uses the exact new destination snapshot.

## Offline

With Yandex cache already populated, disconnect internet and create/preview plans. This must work. Enqueue itself need not fetch network content; actual Downloads transfer naturally requires network.

## Restart / history

Restart MusicArk and verify current plan/history/status/operation results persist. Rebuild creates a new plan id rather than rewriting the old snapshot. Cancelling a planned plan changes only its status and does not cancel unrelated Downloads.

## Safety audit

After all scenarios verify:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing audio/tags = 0
Yandex likes/playlist mutations = 0
Yandex upload/replacement = 0
```

Verify sync tables/audit/logs contain no Yandex token, auth header, cookie or temporary direct download URL.

## Regression

Run v0.7 Local Playback checks (play/pause/seek/navigation) and confirm Sync work did not modify the player. Run existing Yandex, Local Library, Matching, Variant, Coverage and Download workflows.

## Automated commands

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

Do not claim real Windows/Yandex/manual validation until these scenarios actually run.
