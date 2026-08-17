# MusicArk

[Русская версия](README.md)

**Current version: 0.8.2 — Local Metadata Editor & Yandex Metadata Import.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. v0.8.2 adds a separate **explicit-write** workflow for metadata of existing local files.

## Product loop

```text
Yandex Library = desired state
        ↓
Local Library = actual files (normal Scan is read-only)
        ↓
Matching + Variant + Coverage
        ↓
Missing / Wanted → Download / Controlled Sync
```

For files with broken tags there is now a manual repair workflow:

```text
Local Library
  → Edit Metadata
  → local edit
      or
    Yandex Track search → Compare
  → Apply Metadata
      or
    Apply + Bind
  → transactional MP3 write
  → single-file reindex + SHA-256
  → targeted Matching refresh
  → Coverage/UI refresh
```

## Metadata and identity are separate

**Apply Metadata** changes only selected non-empty metadata/artwork and runs normal Matching again. Even 100% similarity alone does not become a user-confirmed identity.

**Apply + Bind** is a separate explicit confirmation and persists:

```text
provider   = yandex_music
external   = <Yandex Track ID>
local file = <Local File ID>
method     = exact_id
confidence = 1.0
reason     = user_confirmed
```

The bind also stores trusted ID3 TXXX provenance, allowing provider identity to be recovered after database deletion, file rename or relocation. Reserved provenance tags are read-only in the normal Advanced Tags editor.

## File mutation safety

Normal Scan, Matching, Coverage and Sync **do not modify user audio files**. An existing file changes only after an explicit Metadata Editor action.

The MP3 writer uses:

```text
original
  ↓
same-directory temporary copy
  ↓
ID3/artwork write
  ↓
MPEG audio validation
  ↓
metadata read-back validation
  ↓
atomic os.replace()
```

Before the atomic replace the original remains unchanged. The audio stream is never transcoded. Basic Save mutates only requested frames and preserves unknown/custom tags.

## Artwork

Local Library displays a thumbnail for each track with this priority:

1. embedded artwork;
2. already-cached Yandex artwork for a confirmed identity;
3. placeholder.

Library rows never perform a per-track Yandex request and Flutter receives cache paths rather than large base64 payloads.

## Yandex metadata import

Search and full Track DTO lookup stay inside Python/backend through the existing Yandex provider/auth boundary. Flutter never receives the Yandex token, Authorization headers, cookies, signed URLs or direct media URLs.

Compare supports selective field/artwork import. Empty Yandex fields do not silently erase non-empty local values.

## Formats

The editor is format-adapter based. v0.8.2 provides the first full safe writer for **MP3/ID3**. Other audio formats remain read-only in the editor until transactional adapters are implemented.

## Controlled Sync

Sync remains a read-only planner/executor over existing layers and is not a bidirectional filesystem mirror. Normal Sync Apply still performs:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations = 0
```

Metadata Editor is a separate explicit-write workflow and is never called automatically by Scan/Matching/Coverage/Sync.

## SQLite

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync
1.8.1 — Rich Yandex download metadata/provenance
1.8.2 — Local artwork cache / Metadata Editor support
```

## Windows development run

```powershell
py -3 -m venv .venv
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
v0.8.0 — Controlled Sync
v0.8.1 — Rich Yandex download metadata/provenance
v0.8.2 — Local Metadata Editor / Yandex Metadata Import
next   — stabilization / TBD
```

See `docs/versions/v0.8.2.md` and `docs/architecture/metadata-editor.md`.
