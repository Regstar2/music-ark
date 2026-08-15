# MusicArk

[Русская версия](README.md)

**Current version: 0.6.0 — Missing Tracks / Library Coverage.**

MusicArk is a Windows desktop application that combines a cached Yandex Music library with a read-only local music collection. v0.5.0 establishes provider-track ↔ local-file identity, v0.5.1 separately verifies the recording/version, and v0.6 adds **Library Coverage / Missing Tracks** above those authoritative results.

## Current product flow

### Yandex Music

- secure Yandex Music OAuth token sign-in through the OS credential store;
- cache-first session, Liked tracks, playlists, and offline cache;
- collection occurrences are deduplicated by `(provider_id, external_id)` for matching and coverage.

### Local Library

- multiple roots, native Windows folder picker, recursive scan;
- structured title/artists/album/duration and technical metadata;
- incremental rescan, SQL search/sort/pagination;
- audio files remain read-only.

### v0.5.0 — Identity Matching

```text
Yandex cache + Local Library
             ↓
      MatchingService
             ↓
 MATCHED / CONFLICT / UNMATCHED
```

Identity matching keeps its precision-first policy:

```text
AUTO MATCH >= 0.90 and best-vs-second margin >= 0.04
CONFLICT   >= 0.70
UNMATCHED   < 0.70
```

Manual accept/reject remains persistent, automatic reruns do not overwrite a manual link, and candidate generation remains bounded rather than forming a full `Yandex × Local` Cartesian product.

### v0.5.1 — Variant Verification

```text
MATCHED / manually accepted identity
             ↓
    VariantDetectionService
             ↓
      metadata evidence
             ↓
      exact reference?
             ↓
       decoded audio
             ↓
SAME / ALTERED / DIFFERENT_VERSION /
UNCERTAIN / NOT_CHECKED
```

Identity confidence and variant/audio evidence are never collapsed into one confidence score.

Metadata-level analysis recognizes semantic markers including Live, Remix/Mix, Acoustic, Instrumental, Remaster(ed), Radio Edit/Version, Edit, Extended, Demo, Clean, Explicit, Censored, and Uncensored.

Yandex `content_warning → explicit` is variant evidence only. An explicit mismatch alone does not prove that a local file is censored or uncensored.

### v0.6 — Library Coverage / Missing Tracks

v0.6 does not build another matching engine. `LibraryCoverageService` and the SQL-backed `CoverageRepository` consume active Yandex membership, `matching_results`, `track_links`, Local Library, and `track_variant_results` and derive:

```text
covered       — current accepted local identity match
missing       — current authoritative UNMATCHED without an accepted local link
needs_review  — CONFLICT / stale manual / invalid accepted link
not_analyzed  — no current matching result or stale automatic result
```

Identity coverage, variant state, and user triage are independent dimensions. A matched identity remains `covered` for `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED`. `CONFLICT` and `not_analyzed` never become `missing`.

The **Missing Tracks** section defaults to Missing and supports summary, All/Liked/playlist scopes, membership, playlist order, search, sort, pagination, secondary variant filters, details, navigation to the existing Matching workflow, and persistent `wanted / ignored / unreviewed` triage including bulk actions.

Future v0.7 input is:

```text
coverage_status = missing
AND user_action = wanted
```

## Reference audio

Deep v0.5.1 verification accepts only the strict existing convention:

```text
.musicark/downloads/yandex/yandex_<track_id>.<ext>
.musicark/downloads/yandex/yandex-<track_id>.<ext>
```

An incidental number elsewhere in a path is not a Yandex ID. The current tested v0.5.1 implementation may acquire **one exact reference during an explicit single-track `variant_run`** when needed; batch verification does not silently download an entire library.

A cached reference is **not Local Library coverage**. It is not inserted into `local_audio_files`, does not create `track_links`, and never establishes `covered` by itself.

## Decoded-audio verification

MusicArk compares decoded audio rather than MP3/FLAC bytes. SHA-256 equality is not used as proof that two encodings are the same recording.

```text
FfmpegAudioDecoder
    ↓
mono / signed-16 PCM / 11025 Hz via pipe
    ↓
bounded alignment ±15 s
    ↓
2.0 s windows / 0.75 s hop
    ↓
energy + spectral + waveform evidence
    ↓
merged altered regions
    ↓
VariantClassifier
```

Adjacent divergent windows are merged into user-visible regions; isolated mild outliers are ignored.

### Optional ffmpeg capability

ffmpeg is not a hard application dependency. Without ffmpeg, Yandex, Local Library, v0.5 identity matching, and v0.6 Coverage continue to work. Technical decoder errors never become `DIFFERENT VERSION`.

## Classification policy

- `SAME`: compatible metadata plus consistently high decoded-audio evidence and no significant altered region;
- `ALTERED`: most of the recording matches, but a small number of persistent localized regions diverge;
- `DIFFERENT VERSION`: strong semantic/duration/distributed-audio evidence indicates a different version;
- `UNCERTAIN`: signals conflict or lie near policy boundaries;
- `NOT CHECKED`: verification has not run, no reference is available, or audio verification is unavailable.

If provider explicit metadata, close duration, high overall recording similarity, and localized divergence agree, MusicArk may add `possible_clean_or_censored_variant`. This is a possibility, not guaranteed lyric/censorship recognition.

## Cache / performance

Audio work starts only after v0.5 identity matching. Variant cache invalidation uses independent provider/local/reference/analyzer fingerprints; a changed pair is recomputed on the next verification run.

Coverage summary/list/search/filter/sort/pagination are SQL-backed. Flutter does not materialize the full 5k–20k provider library to derive status. Global coverage deduplicates `(provider_id, external_id)` across Liked/playlists, while playlist scope keeps provider order.

## UI

The Matching page continues to display identity and variant state separately. The new **Missing Tracks** page adds coverage summary and triage without reimplementing candidate/matching details.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage user actions
```

`track_variant_results` stores analytical status/evidence/fingerprints only. v1.6 adds only `provider_track_actions(provider_id, external_id, action, created_at, updated_at)`; no row means `unreviewed`. Existing Yandex cache, Local Library, matching/manual/conflict state, and variant results are preserved.

## Safety / privacy

- no external matching/metadata/fingerprint API;
- v0.6 does not download missing tracks;
- bounded v0.5.1 reference acquisition is verification-only, not the Download product flow;
- no local audio rename/move/delete/edit/transcode;
- no Yandex Music mutation;
- no PCM persisted in SQLite or transferred through Flutter ↔ Python.

## Windows development run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -p "test_*.py" -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

## Manual Windows validation

Validate summary against Matching on a real library, all four coverage states, Liked/playlist scopes and order, `MATCHED + DIFFERENT_VERSION`, wanted/ignored/bulk triage across restart, matching rerun, offline Coverage, and `strict reference exists + no accepted Local Library link → MISSING`.

## Roadmap

```text
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant / Altered Track Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download
v0.8   — Sync
```

Download/source selection, playback, metadata mutation, and sync are outside v0.6.

See `docs/versions/v0.6.0.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
