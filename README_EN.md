# MusicArk

[Русская версия](README.md)

**Current version: 0.7.0 — Download.**

MusicArk is a Windows desktop application that connects a cached Yandex Music library with a local music collection. v0.5 establishes identity, v0.5.1 independently verifies recording variants, v0.6 derives Library Coverage / Missing Tracks, and v0.7 closes the user loop by acquiring explicitly requested missing tracks through the supported authorized provider workflow.

## Product loop

```text
Yandex Library
      ↓
Local Library
      ↓
Identity Matching
      ↓
Missing Tracks / Coverage
      ↓
Wanted
      ↓
Download Queue
      ↓
authorized Yandex download
      ↓
normal Local Library index
      ↓
exact provider/local identity
      ↓
Coverage = covered
```

A normal v0.7 candidate must satisfy exactly:

```text
coverage_status = missing
AND user_action = wanted
```

`needs_review`, `conflict`, `not_analyzed`, already `covered` tracks, and `MATCHED + DIFFERENT_VERSION` are never automatically downloaded.

## Yandex Music

- Yandex Music OAuth token sign-in through the OS credential store;
- cache-first session, Liked tracks, playlists, and offline cache;
- one provider identity `(yandex_music, external_id)` regardless of collection memberships;
- v0.7 reuses only the existing authenticated Yandex Music download workflow and capabilities available to the current account/API.

MusicArk v0.7 does **not** implement YouTube ripping, VK scraping, torrent search/download, pirate indexes, DRM circumvention, subscription/access bypass, or automatic fallback to another source.

## Local Library

- multiple roots and native Windows folder picker;
- structured title/artists/album/duration/codec and technical fields;
- incremental scan and SQL search/sort/pagination;
- existing music remains read-only: MusicArk does not rename, move, delete, transcode, or edit tags on existing files.

A downloaded file is a newly created file, but after transfer it enters the same v0.4 Local Library pipeline: `LocalMetadataReader` plus `LocalLibraryStorageRepository`, including a real `library_root_id` and `normalized_path`.

## Identity / Variant / Coverage remain independent

Identity Matching v0.5 answers whether provider/local objects represent the same track (`MATCHED / CONFLICT / UNMATCHED`). Variant v0.5.1 separately answers whether the accepted identity is the same recording/version (`SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED`). Coverage v0.6 derives:

```text
covered       — current accepted local identity
missing       — authoritative UNMATCHED without accepted local link
needs_review  — conflict/stale/invalid accepted link
not_analyzed  — missing or stale matching state
```

After an exact provider download, MusicArk already knows the source identity and does not run fuzzy matching to rediscover it. It persists an accepted `exact_id` link. v0.7 **does not fabricate `Variant = SAME`**; variant state remains an independent analysis result.

## v0.7 Download

### Destination

The user selects a folder through the existing Windows folder picker. It becomes a Local Library root or is associated with an existing parent root. The managed destination is:

```text
<Local Library root>\MusicArk\
```

The selected root is persisted in SQLite, while each queued task snapshots its target/root so changing the default later does not silently move existing queued work.

Windows-safe filenames include a stable provider identity, for example:

```text
Artist - Title [yandex_123456].mp3
```

### Queue

User-visible lifecycle:

```text
queued
running
completed
failed
cancelled
skipped
```

`paused` is not exposed because true pause/resume is not implemented. The v0.7 worker is intentionally sequential (`max concurrency = 1`) for predictable SQLite and filesystem semantics.

The queue persists in SQLite. A persisted `running` task after a crash/restart is recovered to retryable `failed / interrupted`. Re-enqueueing the same active Yandex identity does not create a duplicate task.

### Streaming / progress / cancellation

Yandex HTTP content is streamed directly to disk rather than stored as an audio blob in memory/SQLite:

```text
final.mp3.part
      ↓ success
final.mp3
```

When `Content-Length` is known, UI progress uses downloaded bytes / total bytes / percentage. Unknown length renders indeterminate progress. SQLite writes are throttled rather than performed for every 64 KiB chunk.

Running cancellation is cooperative: the worker checks persisted `cancel_requested` between chunks. `.part` is removed and never promoted. v0.7 does not claim HTTP Range resume; Retry restarts the transfer.

### Post-download quality gate

A task is `completed` only after the full chain succeeds:

```text
network complete
  + non-empty atomic final file
  + LocalMetadataReader can parse audio
  + Local Library indexing with non-NULL root_id
  + exact provider/local link
  + Coverage refresh == covered
```

HTTP success alone is never enough.

## Credentials / privacy

Production Download reads the Yandex token from `SystemCredentialStore` and passes it directly to the provider adapter. Tokens and temporary direct download URLs are forbidden in argv, `download_tasks`, `raw_payload_json`, SQLite, filenames, UI details, and audit logs.

Local Library data is not sent to external services except for the minimum provider request required for the explicitly selected provider track.

## Reference audio is not the Download Library

The v0.5.1 exact-reference cache remains separate:

```text
.musicark/downloads/yandex/yandex_<id>.<ext>
```

It is analysis input for Variant verification, not user Local Library content, never establishes Coverage by itself, and is not the destination for normal wanted downloads.

## UI

Primary navigation is now:

```text
MusicArk
├── Yandex Music
├── Local Library
├── Matching
├── Missing Tracks
└── Downloads
```

After a Missing row is marked **Wanted**, the row can be enqueued. The Downloads page provides summary counters, filters, persistent target selection, queue execution, real/indeterminate progress, Retry, Cancel, and completed-history cleanup. Clearing task history never deletes downloaded audio files.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage user actions
1.7.0 — Download queue/progress/settings
```

v1.7 extends the existing `download_tasks` table rather than introducing a parallel v2 queue. Forward migration preserves Yandex cache, Local Library, matching/manual/conflict state, Variant results, wanted/ignored decisions, and legacy download rows.

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

## Roadmap

```text
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download
v0.8   — Sync
```

See `docs/versions/v0.7.0.md`, `docs/architecture/architecture.md`, and `docs/testing/manual-test-plan.md`.
