# MusicArk

[Русская версия](README.md)

**Current version: 0.5.1 — Variant / Altered Track Detection.**

MusicArk is a Windows desktop application that combines a Yandex Music library with a local music collection. v0.5.0 establishes provider-track ↔ local-file identity; v0.5.1 adds a **separate** verification layer that asks whether the accepted pair is the same recording/version.

## Current product flow

### Yandex Music

- secure Yandex Music OAuth token sign-in through the OS credential store;
- cache-first session, Liked tracks, playlists, and offline cache;
- collection occurrences are deduplicated by `(provider_id, external_id)` for matching.

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

## Reference audio

Deep audio verification requires a local reference for the exact provider ID. Only the strict existing convention is accepted:

```text
.musicark/downloads/yandex/yandex_<track_id>.<ext>
.musicark/downloads/yandex/yandex-<track_id>.<ext>
```

Example:

```text
.musicark/downloads/yandex/yandex_69046542.mp3
```

An incidental number elsewhere in a path is not a Yandex ID. MusicArk does **not** download references automatically.

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

ffmpeg is not a hard application dependency. Check it with:

```powershell
ffmpeg -version
```

Without ffmpeg, Yandex, Local Library, and v0.5 identity matching continue to work. Variant audio verification remains conservative and the UI explicitly reports that ffmpeg was not found. A technical decoder error never becomes `DIFFERENT VERSION`.

## Classification policy

- `SAME`: compatible metadata plus consistently high decoded-audio evidence and no significant altered region;
- `ALTERED`: most of the recording matches, but a small number of persistent localized regions diverge;
- `DIFFERENT VERSION`: strong semantic/duration/distributed-audio evidence indicates a different version;
- `UNCERTAIN`: signals conflict or lie near policy boundaries;
- `NOT CHECKED`: verification has not run, no reference is available, or audio verification is unavailable.

If provider explicit metadata, close duration, high overall recording similarity, and localized divergence agree, MusicArk may add `possible_clean_or_censored_variant`. This is deliberately phrased as a possibility, not guaranteed lyric/censorship recognition.

## Cache / performance

Audio work starts only after v0.5 identity matching. It is never performed across every Yandex/local combination.

Variant cache invalidation uses independent fingerprints for provider variant metadata, local path/size/mtime, reference path/size/mtime, and `ANALYZER_VERSION`. Unchanged successful pairs avoid redundant decode; local/reference/provider/analyzer changes force recomputation.

`Verify all available` is limited to matched pairs with exact references. PCM remains Python-side and never crosses the Flutter bridge.

## UI

The Matching page displays identity and variant state separately, for example:

```text
MATCHED 98%
Version: SAME
```

The detail dialog has independent **Identity** and **Variant verification** sections with audio similarity, reasons/signals, altered regions, reference path, and a **Verify Version** action. A controlled **Verify all available** batch is also available.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
```

`track_variant_results` stores analytical status/evidence/similarity/regions/fingerprints only; it does not store PCM/audio blobs. Existing Yandex cache, Local Library, v0.5 matches, and manual decisions are preserved.

## Safety / privacy

- no external matching/metadata/fingerprint API;
- no automatic reference download;
- no local audio rename/move/delete/edit/transcode;
- no Yandex Music mutation;
- no PCM persisted in SQLite or transferred through Flutter ↔ Python.

## Windows development run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

GitHub Actions are not used for the v0.5.1 validation milestone; checks are run locally.

## Manual Windows validation

Use a small controlled set covering same recording MP3↔FLAC, gain/encoding changes, clean/explicit variants when legally available, Radio Edit, Live, Remix, a short silence/tone edit on owned/test audio, a small leading offset, missing ffmpeg, and corrupt/missing test files.

Primary quality gate: an obviously different version must not be automatically displayed as `SAME`.

## Roadmap

```text
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant / Altered Track Detection
v0.6   — Missing Tracks
v0.7   — Download
v0.8   — Sync
```

Download, the Missing Tracks product workflow, playback, metadata editing, and sync are outside v0.5.1.

See `docs/versions/v0.5.1.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
