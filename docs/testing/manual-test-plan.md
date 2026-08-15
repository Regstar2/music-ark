# Manual Test Plan — MusicArk v0.5.1

Use the real cached Yandex Library together with a disposable/local test collection such as `C:\MusicArk-Test`. Do not delete `.musicark\musicark.db`, saved Yandex credentials, or music files for this test.

## Preconditions

- Windows Flutter desktop target works;
- existing v0.5 database/manual decisions remain in place so migration `1.4.0 → 1.5.0` is exercised;
- Yandex Liked/playlists are cached;
- Local Library is scanned;
- v0.5 matching has representative `MATCHED`, `CONFLICT`, and `UNMATCHED` rows;
- optional ffmpeg is installed for deep-audio cases; a separate run without ffmpeg is also required;
- any manual edited-audio fixtures are copies of owned/test material, never the primary music archive.

## Migration / v0.5 regression

1. Launch v0.5.1 against the existing v0.5 database.
2. Confirm schema becomes `1.5.0` automatically.
3. Confirm Yandex saved session, Liked, playlists, and cached tracks remain available.
4. Confirm Local Library roots/tracks/search/sorting remain available.
5. Confirm previous `MATCHED / CONFLICT / UNMATCHED` results still exist.
6. Confirm a v0.5 manual accepted link still has manual precedence.
7. Confirm no database deletion/rescan is required merely for migration.

## Identity Matching baseline

Repeat the v0.5 precision checks before evaluating variants:

- obvious title+artist/duration matches stay correct;
- ambiguous candidates remain `CONFLICT`/`UNMATCHED` rather than false `MATCHED`;
- manual accept/reject persists across restart/rerun;
- duplicate Liked/playlist membership remains one provider identity;
- deleted local files invalidate links after Local Library rescan.

Variant work must not change the meaning of identity status or confidence.

## Variant UI baseline

1. Open **Сопоставление**.
2. For a matched row confirm the identity badge remains `MATCHED` and a separate variant badge appears.
3. Before analysis the variant state may be `NOT CHECKED`.
4. Open detail and confirm separate **Identity** and **Variant verification** sections.
5. Confirm identity confidence is not displayed as audio similarity.
6. Confirm `Проверить версию` is available on matched rows.
7. Confirm unresolved conflict/unmatched rows do not trigger audio analysis.
8. Use **Проверить все доступные** and confirm progress/busy state remains visible while the Python-side batch runs.

## Reference resolver

Prepare exact-ID references under `.musicark\downloads\yandex` or as indexed local files:

```text
yandex_69046542.mp3
yandex-69046542.flac
```

Verify:

- exact filenames are accepted;
- `Artist 69046542 - Song.mp3` is not treated as a reference;
- a random directory number is not treated as a reference ID;
- no reference is downloaded automatically.

## Real-library / owned-fixture matrix

Prepare a small controlled set:

### A. Same recording, MP3 ↔ FLAC

Expected: `SAME` when alignment/audio evidence is strong.

### B. Same recording, changed gain/encoding

Create/obtain an owned/test copy with changed volume or encoding. Expected: still `SAME`, not `ALTERED` merely because bytes differ.

### C. Clean / Explicit pair

If both versions are legally available, compare them. Metadata `explicit` alone must not assert censorship. If most audio matches and localized stable divergences exist, `ALTERED` with `possible_clean_or_censored_variant` is acceptable.

### D. Radio Edit

Expected: must not be automatically classified `SAME` merely from title/artist identity. `DIFFERENT VERSION` is preferred when semantic/duration/audio evidence is strong; otherwise `UNCERTAIN` is acceptable.

### E. Live version

Expected: not `SAME`.

### F. Remix

Expected: not `SAME`.

### G. Local 2-second replacement

On a copy of test/owned audio replace a short region with silence or another tone/noise. Expected: `ALTERED`, with one merged altered region around the edited interval rather than dozens of tiny windows.

## Alignment

Add roughly 0.5–2 seconds of leading silence to an owned/test copy. Expected: bounded alignment compensates for the small start offset and a genuinely same recording can remain `SAME`.

A large/unreliable offset must become `UNCERTAIN`, not force an optimistic class.

## Duration / substantially different recording

Test a materially shortened version and a recording that diverges over a large fraction of its duration. Expected: `DIFFERENT VERSION` or conservative `UNCERTAIN` near policy boundaries; never obvious `DIFFERENT VERSION → SAME`.

## Altered regions

For an `ALTERED` result confirm detail contains:

- start time;
- end time;
- mean similarity;
- merged region behavior.

Adjacent bad windows should be merged. A single mild outlier surrounded by normal windows should not automatically create a region.

## ffmpeg unavailable

Run once with ffmpeg unavailable from PATH.

Expected:

- app starts normally;
- Yandex/Local Library/matching remain functional;
- UI shows `Аудиосравнение недоступно: ffmpeg не найден`;
- variant technical state is `NOT CHECKED`/conservative;
- technical failure is never converted to `DIFFERENT VERSION`;
- installing/restoring ffmpeg allows later re-analysis without deleting the DB.

## Cache / invalidation

1. Analyze a pair with a valid reference.
2. Run it again without changes: decoded audio should be reused from the stored result (no second decode).
3. Change the local test file: old variant result must become stale and recompute.
4. Restore local, then change reference: recompute.
5. Refresh provider metadata changing explicit/variant-relevant fields: recompute.
6. Change `ANALYZER_VERSION` in a development test: recompute.
7. Confirm v0.5 identity need not be rebuilt solely because explicit changed.

## Batch resilience / performance

- Use many Yandex identities but only a small subset with exact references.
- Confirm audio verification touches only `MATCHED`/manual accepted pairs with references.
- Confirm no Local Library × Yandex full decode loop occurs.
- Introduce one missing/corrupt/unreadable test file and confirm the rest of the batch continues.
- UI must remain responsive while the external Python analysis process runs.

## Offline / privacy

After caches are populated disconnect network access and run identity + variant analysis. Both must operate locally. No local metadata/audio should be uploaded to Yandex or third-party matching/fingerprint/metadata APIs.

## Safety regression

During all tests verify MusicArk does not:

- rename, move, delete, transcode, or edit local music files;
- alter the reference file;
- create persistent giant decoded WAV files;
- store PCM/audio blobs in SQLite;
- like/dislike tracks, edit playlists, upload, or otherwise mutate Yandex Music;
- automatically download reference tracks;
- delete `.musicark\musicark.db` or saved credentials.

## Automated commands

Do not run GitHub Actions for this milestone. Run locally:

```powershell
python -m unittest discover -s tests -v
cd ui\musicark_ui
flutter analyze
flutter test
flutter run -d windows
```

## Pass criteria

- migration `1.4.0 → 1.5.0` preserves Yandex cache, Local Library, v0.5 matches and manual decisions;
- v0.5 identity semantics/regressions remain correct;
- exact-ID reference resolver rejects incidental numbers;
- same-recording codec/gain cases are not rejected merely because bytes differ;
- localized edits can produce `ALTERED` + merged regions;
- Live/Remix/Acoustic/Instrumental/Radio Edit do not become `SAME` from title/artist alone;
- explicit mismatch without audio does not claim censorship;
- missing ffmpeg/reference/corrupt file fails gracefully;
- unchanged pairs avoid redundant decode and local/reference/provider changes invalidate cache;
- batch remains bounded to matched/reference-available pairs;
- Python tests, Flutter analyzer, and Flutter tests are green on Windows;
- real-library/owned-fixture review is completed before accepting thresholds.
