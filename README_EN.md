# MusicArk

[Русская версия](README.md)

**Current version: 0.5.0 — Matching.**

MusicArk is a Windows desktop application that combines a Yandex Music library with a local music collection. v0.5 adds fully local provider-track ↔ local-file matching and stores confidence plus manual decisions in the shared SQLite database.

## What works in v0.5

### Yandex Music

- secure Yandex Music OAuth token sign-in through the OS credential store;
- cache-first session, Liked tracks, playlists, and offline cache;
- tracks appearing in multiple collections are deduplicated by `(provider_id, external_id)` for matching.

### Local Library

- multiple local roots, native Windows folder picker, and recursive scan;
- structured title, artists, album, album artist, duration, and technical metadata;
- incremental rescan, SQL search/sort/pagination;
- MusicArk does not modify audio files.

### Matching

```text
Yandex cache + Local Library
             ↓
      MatchingService
             ↓
      CandidateGenerator
             ↓
         MatchScorer
             ↓
       MatchDecision
             ↓
 matched / conflict / unmatched
             ↓
            SQLite
```

- a new **Matching** section with summary and Run Matching action;
- All / Matched / Needs review / Unmatched filters;
- search, sorting, and `limit`/`offset`;
- conflict detail with multiple top candidates;
- manual accept (`match_method=manual`) and persistent rejection;
- automatic reruns do not overwrite manual matches;
- a removed local file invalidates the old link;
- `matcher_version=1` plus fingerprints allows changed data to be recalculated safely.

## Matching policy

Candidate generation uses indexed `normalized_title`, `normalized_artists_text`, and duration buckets. At most 40 local candidates reach detailed scoring for each provider track; there is no full `Yandex × Local` Cartesian product.

Normalization uses Unicode NFKC, `casefold`, canonical whitespace/punctuation/dash handling. Multiple artists are compared as an order-independent set. Semantic markers such as `Live`, `Remix`, `Acoustic`, `Instrumental`, `Remaster`, and `Radio Edit` are preserved.

Scoring v1:

```text
title    0.50
artists  0.30
duration 0.15
album    0.05
```

Duration is a secondary signal only. Filename is a fallback. The strict `yandex_<track_id>.<ext>` convention remains a very strong exact-ID signal; an incidental number in a path is not an exact match.

Decision policy:

```text
AUTO MATCH >= 0.90 and best-vs-second margin >= 0.04
CONFLICT   >= 0.70
UNMATCHED   < 0.70
```

When two strong candidates are close, MusicArk chooses `CONFLICT` instead of picking one arbitrarily. Automatic-match precision is the primary quality gate.

## Safety / privacy

v0.5 runs offline after the Yandex cache and Local Library are populated. Local metadata is not sent to Yandex, OpenAI, or third-party matching/metadata APIs. Matching never renames, moves, deletes, or edits audio files and never mutates Yandex Music.

The v0.5 forward SQLite migration is `1.4.0`. Existing `.musicark/musicark.db`, Yandex cache, local index, and credentials must not be deleted.

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

## Manual Windows validation for v0.5

Use the real Yandex Library together with a test local collection such as `C:\MusicArk-Test`. Check obvious exact matches, difficult live/remix/acoustic cases, same-title/different-artist cases, an ambiguous conflict, manual accept/reject, restart, and rerun. Real matching quality is not considered validated until it is checked against the user's actual library.

## Roadmap

```text
v0.1 — Yandex Likes MVP
v0.2 — Persistent Library
v0.3 — Yandex Library / Playlists
v0.4 — Local Library
v0.5 — Matching
v0.6 — Missing Tracks
v0.7 — Download
v0.8 — Sync
```

Download, the Missing Tracks product workflow, playback, metadata editing, and sync are outside v0.5.

See `docs/versions/v0.5.0.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
