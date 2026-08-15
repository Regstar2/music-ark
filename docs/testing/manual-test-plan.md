# Manual Test Plan — MusicArk v0.6.0

Use the real cached Yandex Library together with the real Local Library or a disposable test subset. Do not delete `.musicark\musicark.db`, saved Yandex credentials, matching/manual/variant results, or music files for this test.

## Preconditions

- Windows Flutter desktop target works;
- existing v0.5.1 database/manual decisions remain in place so migration `1.5.0 → 1.6.0` is exercised;
- Yandex Liked/playlists are cached;
- Local Library is scanned;
- v0.5 matching has representative `MATCHED`, `CONFLICT`, and `UNMATCHED` rows;
- v0.5.1 has representative `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED` results where possible;
- optional ffmpeg is installed for deep-audio cases; a separate run without ffmpeg may still be used for v0.5.1 regression;
- any manual edited-audio fixtures are copies of owned/test material, never the primary music archive.

## Migration / regression

1. Launch v0.6 against the existing v0.5.1 database.
2. Confirm schema becomes `1.6.0` automatically.
3. Confirm Yandex saved session, Liked, playlists, and cached tracks remain available.
4. Confirm Local Library roots/tracks/search/sorting remain available.
5. Confirm previous `MATCHED / CONFLICT / UNMATCHED` results still exist.
6. Confirm v0.5 manual accepted/rejected state still has manual precedence.
7. Confirm v0.5.1 variant results remain present.
8. Confirm no database deletion/rescan is required merely for migration.
9. Confirm `provider_track_actions` is created and existing data remains intact.

## Identity Matching baseline

Repeat the v0.5 precision checks before evaluating Coverage:

- obvious title+artist/duration matches stay correct;
- ambiguous candidates remain `CONFLICT`/`UNMATCHED` rather than false `MATCHED`;
- manual accept/reject persists across restart/rerun;
- duplicate Liked/playlist membership remains one provider identity;
- deleted local files invalidate links after Local Library rescan.

Coverage work must not change the meaning of identity status or confidence.

## Coverage truth table

Open **Недостающие** and verify the primary states independently:

- current `MATCHED` / current accepted manual link → `COVERED`;
- current authoritative `UNMATCHED` with no accepted current local link → `MISSING`;
- current `CONFLICT` → `NEEDS_REVIEW`;
- stale manual accepted decision / invalid accepted local link → `NEEDS_REVIEW`;
- no matching result → `NOT_ANALYZED`;
- automatic result stale because matcher/provider/Local Library fingerprint changed → `NOT_ANALYZED`.

Explicitly confirm these forbidden mappings never occur:

```text
CONFLICT      → MISSING
NOT_ANALYZED  → MISSING
STALE         → MISSING
```

## Coverage summary

1. Compare Coverage total with the unique active provider identities in the selected scope.
2. Confirm `covered + missing + needs_review + not_analyzed = total`.
3. Confirm Local coverage uses `covered / total`.
4. Confirm Matching analyzed is shown separately and decreases when `not_analyzed` exists.
5. Confirm variant counts are shown separately from primary coverage counts.
6. Confirm summary for Liked and individual playlists matches their unique provider identities.

## Collection identity / scope

Prepare or find one track present in Liked and at least two playlists.

- Global coverage counts it once.
- Row/detail shows all collection memberships.
- Liked scope includes it once.
- Each relevant playlist scope includes it once.
- A playlist with duplicate occurrences must not create fake provider identities.
- Playlist scope preserves Yandex order.
- A track removed from Liked and every active playlist disappears from active Coverage after refresh.

## Search / sorting / pagination

Verify SQL-backed UI behavior for a library large enough to paginate:

- search by title;
- search by artist;
- search by album;
- search by collection/playlist name;
- sort by Artist / Title / Album / Collection / Status where available;
- playlist-order sort inside playlist scope;
- next/previous pages load only page-sized result sets;
- changing filter/search resets pagination safely.

## Variant separation regression

For current accepted identity matches confirm:

```text
MATCHED + SAME              → COVERED / SAME
MATCHED + ALTERED           → COVERED / ALTERED
MATCHED + DIFFERENT_VERSION → COVERED / DIFFERENT_VERSION
MATCHED + UNCERTAIN         → COVERED / UNCERTAIN
MATCHED + NOT_CHECKED       → COVERED / NOT_CHECKED
```

None may increment Missing.

The **Сопоставление** page must continue to show identity and variant state separately. Identity confidence is not audio similarity.

## Reference resolver / acquisition boundary

Exact-ID references use:

```text
yandex_69046542.mp3
yandex-69046542.flac
```

Verify:

- exact filenames are accepted;
- `Artist 69046542 - Song.mp3` is not treated as a reference;
- a random directory number is not treated as a reference ID;
- an explicit single-track v0.5.1 verification may boundedly acquire one exact reference when the current implementation supports it;
- batch verification does not silently acquire an entire library;
- reference files are not inserted into Local Library and do not create `track_links`.

### Mandatory Coverage reference regression

Create/use one strict reference file where:

```text
reference exists
+
no accepted indexed Local Library link
+
matching = UNMATCHED
```

Expected Coverage: **MISSING**. The reference must never establish `COVERED`.

## User triage

For several current Missing tracks:

1. Mark one **Нужен** (`wanted`).
2. Mark one **Игнорировать** (`ignored`).
3. Leave one unresolved (`unreviewed`).
4. Restart MusicArk and confirm decisions persist.
5. Use bulk selection and apply wanted/ignored/reset.
6. Reset one decision and confirm it becomes unreviewed/no stored action.
7. Confirm ignored remains technically Missing and can be revealed by filters.
8. Confirm no Download button/queue execution exists in v0.6 Coverage.

## Matching change / future download contract

1. Start from `missing + wanted`.
2. Add/scan a matching local file or otherwise rerun existing Matching so the identity becomes current `MATCHED`.
3. Confirm technical Coverage changes to `COVERED` immediately after rerun/refresh.
4. Confirm the historical wanted row may remain stored but does not appear in `status=missing AND user_action=wanted`.

This is the future v0.7 contract.

## Local Library rescan / stale automatic result

1. Record a current `UNMATCHED` row shown as Missing.
2. Change Local Library state by adding/removing/replacing a candidate file and rescan.
3. Before rerunning Matching, confirm the old automatic result is no longer asserted as Missing; it must be `NOT_ANALYZED` / require rematch.
4. Rerun the existing Matching workflow and confirm Coverage follows the new authoritative result.

## Variant UI baseline (v0.5.1 regression)

1. Open **Сопоставление**.
2. For a matched row confirm the identity badge remains `MATCHED` and a separate variant badge appears.
3. Before analysis the variant state may be `NOT CHECKED`.
4. Open detail and confirm separate **Identity** and **Variant verification** sections.
5. Confirm `Проверить версию` is available on matched rows.
6. Confirm unresolved conflict/unmatched rows do not trigger audio analysis.
7. Use **Проверить все доступные** and confirm the batch remains bounded to available references.

## Real-library / owned-fixture variant matrix

Retain the v0.5.1 regression matrix:

- same recording MP3 ↔ FLAC: expected `SAME` when evidence is strong;
- same recording with gain/encoding change: should not become `ALTERED` merely because bytes differ;
- clean/explicit pair, when legally available: metadata alone must not assert censorship; localized audio differences may produce `ALTERED` + `possible_clean_or_censored_variant`;
- Radio Edit / Live / Remix: must not become `SAME` solely from title/artist identity;
- copied owned/test audio with ~2 s silence/tone replacement: expected localized `ALTERED` with merged region;
- small leading offset: bounded alignment should compensate where reliable;
- materially shortened/distributed-different recording: `DIFFERENT_VERSION` or conservative `UNCERTAIN`, never obvious false `SAME`.

## ffmpeg unavailable (variant regression)

Run once with ffmpeg unavailable from PATH.

Expected:

- app starts normally;
- Yandex/Local Library/Matching/Coverage remain functional;
- variant audio verification reports a conservative unavailable/NOT_CHECKED state;
- technical failure never becomes `DIFFERENT_VERSION`;
- restoring ffmpeg allows later variant re-analysis without deleting the DB.

## Offline / privacy

After Yandex cache, Local Library scan, Matching and any desired variant checks are populated, disconnect network access.

Expected:

- Coverage summary/list/search/filter/triage continue working;
- existing Matching/variant data remains usable;
- no local metadata/audio/path/matching/missing-list data is uploaded to Yandex or third-party services.

## Safety regression

During all tests verify MusicArk does not:

- rename, move, delete, transcode, or edit local music files;
- alter reference files;
- promote reference cache into Local Library;
- create persistent giant decoded WAV files;
- store PCM/audio blobs in SQLite;
- like/dislike tracks, edit playlists, upload, or otherwise mutate Yandex Music;
- execute Missing Tracks download/source selection in v0.6;
- delete `.musicark\musicark.db` or saved credentials.

## Automated commands

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter analyze
flutter test
flutter run -d windows
```

## Pass criteria

- migration `1.5.0 → 1.6.0` preserves Yandex cache, Local Library, identity/manual/conflict and variant state;
- v0.5 identity and v0.5.1 variant regression suites remain correct;
- Coverage truth table and stale handling are correct;
- global identity dedup / collection scopes / playlist order are correct;
- reference cache never counts as Local Library coverage;
- wanted/ignored/reset persist and bulk triage works;
- newly matched wanted track leaves active Missing+wanted;
- SQL pagination/search/filter remains responsive on the real library;
- offline Coverage works;
- Python tests, Flutter analyzer, and Flutter tests are green on Windows;
- real-library Coverage/manual review is completed before release acceptance.
