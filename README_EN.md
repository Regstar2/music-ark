# MusicArk

[Русская версия](README.md)

**Current version: 0.8.0 — Controlled Sync.**

MusicArk is a Windows desktop application that connects a cache-first Yandex Music library with a local music collection. v0.5 establishes identity, v0.5.1 independently verifies recording variants, v0.6 derives Coverage/Missing, v0.7 provides production Download + Local Playback, and v0.8 coordinates those existing layers through a safe dry-run Sync Plan.

## Product loop

```text
Yandex Library = desired state
        ↓
all / liked / Yandex Playlist
        ↓
Coverage + Matching + Variant + Local Library = actual state
        ↓
Controlled Sync Planner (read only)
        ↓
Preview / blockers / explicit confirmation
        ↓
execution-time revalidation
        ↓
DownloadService.enqueue() for current Missing + Wanted
        ↓
Downloads → normal v0.7 transfer/index/link/coverage
```

Controlled Sync is not a bidirectional filesystem mirror.

## Policy

Provider identity is `(provider_id, external_id)`. One identity present in Liked and several playlists is planned once; duplicate playlist occurrences do not create duplicate downloads.

```text
covered                      → no acquisition
missing + wanted             → ENQUEUE_DOWNLOAD
missing + unreviewed         → USER_DECISION_REQUIRED
missing + ignored            → summary / no download
needs_review                 → REVIEW_IDENTITY
not_analyzed                 → matching review blocker
covered + uncertain/altered/
different_version            → REVIEW_VARIANT
```

`DIFFERENT_VERSION` never becomes Missing and never causes automatic replacement. v0.7 direct single-track Download remains a separate explicit user intent and does not loosen bulk Sync policy.

## Safety and staleness

Each plan is an immutable snapshot containing planner version, scope, exact target, input fingerprint, summary and operations. Relevant active Yandex membership, Matching/Local state, triage or target changes make a plan stale. Playback state is deliberately excluded.

Apply requires confirmation and rechecks every actionable identity immediately before enqueue. It then delegates to production `DownloadService.enqueue()`. Sync never calls `runQueue()`, never starts unrelated queued work and does not implement its own HTTP download path.

Normal v0.8 Apply performs zero local delete/move/rename/tag mutations and zero Yandex mutations. Local-only/Outside selected scope is informational only.

## Existing layers

Yandex Library, Local Library, Identity Matching, Variant, Coverage, Download and embedded Local Playback remain separate authoritative layers. Sync coordinates them rather than reimplementing them.

## UI

```text
MusicArk
├── Yandex Music
├── Local Library
├── Matching
├── Missing Tracks
├── Downloads
└── Sync
```

The Sync page shows scope, target, Current/Projected coverage, download candidates, undecided Missing, matching/identity blockers, Variant review, Local-only/Outside scope, stale/legacy state, explicit confirmation, Apply results and persisted plan history.

## SQLite

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync snapshots/results
```

The `1.7.0 → 1.8.0` forward migration extends existing `sync_plans` / `sync_operations` in place and preserves legacy rows. Legacy upload/replace/metadata plans remain viewable but cannot execute through the v0.8 executor.

Yandex tokens, auth headers, cookies and temporary direct URLs are never persisted in sync metadata.

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
v0.7   — Download + Local Playback
v0.8   — Controlled Sync
next   — TBD / stabilization
```

See `docs/versions/v0.8.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`, and `docs/release/release-checklist.md`.
