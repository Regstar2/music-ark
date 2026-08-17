# MusicArk

[Русский](README.md) · **English**

**Current code version: 0.9.0 — UI, Account & Settings.**  
**Current SQLite schema: 1.8.4.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers; v0.9.0 adds a unified application shell, global account state, settings, light/dark themes, RU/EN localization infrastructure, offline Help and diagnostic About information.

## Desktop shell v0.9.0

`Settings` and the account control live in the utility area at the bottom of the global left sidebar. Without a stored Yandex session the control shows `Sign in`; when authenticated it shows the account name and an initials fallback avatar. Sign-in reuses the existing Yandex workflow and logout uses the existing backend boundary. Account bootstrap remains cache-first and does not require a network request on every launch.

UI settings apply without restart and are stored separately from the music SQLite database:

- theme: `System` / `Light` / `Dark`;
- language: `System` / `Russian` / `English`;
- Help remains available offline;
- About reports app/backend/schema versions, OS information and safe diagnostics without tokens or library contents.

MusicArk uses standard Flutter `ThemeMode`, Material 3 `ColorScheme`, and `gen_l10n`/ARB resources. Theme/locale changes rebuild the application presentation without recreating the shell state that owns the current Yandex playlist and Now Playing lifecycle.

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

Files with broken tags use a separate manual workflow:

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

**Apply Metadata** changes only selected non-empty fields, artwork and an explicitly selected filename for the local MP3. The write is followed by a single-file reindex, SHA-256 refresh and targeted Matching refresh. High similarity alone never becomes a user-confirmed identity.

**Apply + Bind** performs the same write and additionally persists the explicit relation:

```text
provider   = yandex_music
external   = <Yandex Track ID>
local file = <Local File ID>
method     = exact_id
confidence = 1.0
reason     = user_confirmed
```

The bind also stores trusted ID3 TXXX provenance. Reserved provenance tags are read-only in the normal Advanced Tags editor.

## File mutation safety

Scan, Matching, Coverage and Sync **do not modify user audio files**. An existing file changes only after an explicit Metadata Editor action.

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

Before the atomic replace the original remains unchanged. The audio stream is not transcoded. Unknown/custom ID3 frames are preserved unless the user explicitly edits them.

## Artwork and Yandex Library playback

Local Library displays a thumbnail for each track. Priority is embedded artwork, then already-cached Yandex artwork for a confirmed identity, then a placeholder. Local Library rows never perform a per-track Yandex request.

Yandex Library provides artwork and built-in playback. The backend prepares or reuses a private cache under `.musicark/playback/yandex` and passes only the local path to Flutter. The Yandex token, Authorization headers and protected/signed provider media URLs are never passed to Flutter. Playback-cache files are not indexed into Local Library and do not affect Matching or Coverage.

The Yandex workspace keeps a minimum width of about `920 px`; narrower windows use horizontal scrolling. This remains a desktop safeguard rather than a mobile/responsive redesign.

## Content labels and Variant acceptance

App-level **ORIGINAL / CENSORED** marks can be stored for a local track and a cached Yandex identity. They do not mutate Yandex, rewrite audio metadata, change Matching identity or increase confidence.

For `ALTERED`, `DIFFERENT_VERSION` and `UNCERTAIN`, the user may accept the current recording and later undo that acceptance. The decision is stored separately from the analyzer result: the original Variant status does not become `SAME`. Acceptance remains valid only while the analysis evidence/fingerprint is unchanged.

## Formats

The editor uses format adapters. Full safe writing is implemented for **MP3/ID3**. Other audio formats remain read-only in Metadata Editor.

## Controlled Sync

Sync is not a bidirectional filesystem mirror. Normal Apply remains constrained to:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations = 0
```

Metadata Editor is a separate explicit-write workflow and is never called automatically by Scan/Matching/Coverage/Sync.

## SQLite

Forward-only schema:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync
1.8.1 — Rich Yandex download metadata/provenance
1.8.2 — Local artwork cache / Metadata Editor support
1.8.3 — app-level ORIGINAL/CENSORED labels
1.8.4 — variant user acceptance
```

v0.9.0 does not bump the SQLite schema: theme/locale preferences use a separate UI-only typed store. Database initialization remains idempotent and does not require deleting an existing `.musicark/musicark.db`.

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
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata       complete
v0.9.0 — UI, Account & Settings                        current
v0.10.x — Yandex Upload                                next
```

Yandex Upload is not implemented in v0.9.0. This describes source state and does not claim that a public GitHub Release exists. See `docs/versions/v0.9.0.md`, `docs/architecture/app-shell-settings.md`, `docs/architecture/metadata-editor.md`, `docs/architecture/content-labels.md` and `docs/architecture/variant-acceptance.md`.
