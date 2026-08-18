# MusicArk

[Русский](README.md) · **English**

**Current code version: 0.9.5 — Downloads UI, Safe Deletion & Bulk Actions.**  
**Current SQLite schema: 1.8.4.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. v0.9.5 redesigns the Downloads workspace, adds safe removal of failed task records and explicit batch actions without turning queue-history removal into audio-file deletion.

## Downloads v0.9.5

`Downloads` now uses compact counted `Downloads` / `Wanted` tabs, separate summary metrics, search/status filters, compact lazy-rendered track rows and contextual bulk actions. User-facing failures are mapped from `errorCode`; the raw backend message plus task/provider/external IDs remain available separately in Technical details.

`failed` and `needs_review` tasks have an explicit `Remove` action. It deletes only the persisted download-task record; the final audio file, Local Library, Matching, Coverage, Wanted state, provider cache and audit history are not deleted. The expected sibling `.part` may be cleaned best-effort only after a safe-path check. `queued`/`running` tasks cannot be removed directly and continue to use cancellation.

Multi-selection supports retrying failed tasks, cancelling active tasks, removing failed tasks and `Download selected` in Wanted. The batch bridge sends ID sets through one Python process and returns partial results. `Retry selected` and `Download selected` execute only task IDs created or changed by the current action and do not wake unrelated old queue entries.

## Coverage / Missing v0.9.4

The `Missing` section now centers the track list instead of a long technical statistics row. The page starts with a compact local-coverage card and progress meter, four primary metrics, collapsible Matching/Variant analysis details, counted status tabs and a responsive Collection/Search/Decision/Sort/Variant toolbar.

Coverage rows use the already-persisted `ProviderTrack.artwork_url` with a local placeholder when artwork is missing or fails to load, followed by title, artist/album, collection membership and separate Coverage/Variant badges. Flutter does not construct provider URLs or receive the Yandex token, cookies or Authorization headers.

Missing actions keep their existing semantics: `Download` runs the current direct Download workflow without changing `userAction`; `Wanted`, `Ignore` and `Reset` remain triage state. The master checkbox selects all results in the active Missing filter, and pagination is hidden when the filtered result fits on one page.

## Matching v0.9.3

The `Matching` section presents results as a desktop-oriented comparison workspace:

```text
Yandex Music | Local file | Confidence | Status
```

The page starts with separate summary cards for Yandex/Local track counts, Matched, Needs review and Not found, followed by Matching/Variant actions, counted filters, Search and Sort. Confidence is presented as a compact percentage plus progress meter instead of a large circular indicator.

Matching status and Variant status remain separate concepts: Matching establishes identity, while Variant checks the recording/version. Clicking a row still opens the existing detail workflow with Yandex/Local comparison, ORIGINAL/CENSORED labels, Variant verification/acceptance and manual decisions for conflict candidates.

Search/Sort/filters continue to use the existing bridge query contract; pagination preserves the active query scope and reports `Shown X of Y`. On narrower desktop windows the comparison table scrolls horizontally instead of collapsing its semantic columns. v0.9.3 adds no per-row network artwork requests, no new Matching/Variant algorithm and no SQLite migration.

## Local Library v0.9.2

Local Library uses the same desktop presentation layer as the rest of MusicArk: a compact header, one toolbar, a separate source-management section and a responsive table-like track list.

The `Folders` filter can display:

```text
all folders
one folder
any subset of folders
no folders
```

Folder selection is **view scope only**, not library configuration. Adding, scanning and removing configured source roots remain separate explicit actions.

Filtering is performed in SQLite rather than against only the first Flutter page:

```text
Local Library UI
  → rootIds
  → Flutter process bridge
  → LocalLibraryService
  → SQLite library_root_id IN (?, ...)
  → COUNT / search / sort / LIMIT / OFFSET
```

Query semantics:

```text
rootIds = null    → all configured roots
rootIds = []      → 0 tracks
rootIds = [1]     → root 1 only
rootIds = [1,3]   → union of roots 1 and 3
```

All roots are selected on first open. If a root is added while the user is viewing all roots, the new root joins the view automatically; when the user has an explicit subset, the new root is not selected automatically. Removed root IDs are reconciled out of the selection.

Search, Sort and Load More always use the same selected root subset. Artwork, playback, Metadata Editor, details, reveal-in-filesystem and ORIGINAL/CENSORED remain available.

## Desktop shell and Yandex UI v0.9.1+

MusicArk uses one permanent global left sidebar. The second permanent Yandex Music sidebar is removed: `Tracks`, `Playlists` and `Albums` use top-level navigation inside the main workspace.

The `Albums` tab shows **albums that the user explicitly liked in Yandex Music**. This is a separate cache-first provider collection: the liked-album index refreshes with the library, while tracks for an individual album are loaded lazily when opened and are then cached by MusicArk. Albums are not inferred from album tags on liked tracks. No music-database schema bump is required because the existing generic provider-collection storage is reused.

The Yandex workspace uses the available window width instead of the old mandatory `~920 px` horizontal-scroll layout. Search, sort and `Version labels` reflow on narrower desktop windows; the track list uses a table-like layout when wide and a compact row layout when space is tighter. Track sorting also includes `Unavailable first`.

The normal technical `available` value is not rendered on every track. Unavailable tracks are visually muted, playback is disabled, and the reason is exposed through a tooltip. ORIGINAL/CENSORED remain app-level labels.

The global sidebar uses shared layout tokens and a small vector MusicArk mark. `System / Light / Dark`, `System / Russian / English`, account control, Settings, Help and About remain supported. Now Playing stays application-wide and responsive without adding queue/next/previous/shuffle/repeat semantics.

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

Scan, root view filtering, Matching, Coverage and Sync **do not modify user audio files**. An existing file changes only after an explicit Metadata Editor action. Removing a failed/needs-review download task in v0.9.5 also does not delete the final audio file.

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

Downloads v0.9.5 uses a local placeholder when the current download payload has no ready artwork; it adds no per-row network artwork request.

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

v0.9.5 does not bump the SQLite schema. Safe task removal reuses the existing `download_tasks` storage, and the batch command adds no table or column. Database initialization remains idempotent and does not require deleting an existing `.musicark/musicark.db`.

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
v0.9.0 — UI, Account & Settings                        complete
v0.9.1 — Main Screen UI Polish                         complete
v0.9.2 — Local Library UI & Multi-Root Selection       complete
v0.9.3 — Matching UI Redesign                          complete
v0.9.4 — Coverage / Missing UI Polish                  complete
v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions    current
v0.10.x — Yandex Upload                                next
```

Yandex Upload is not implemented in v0.9.5. This describes source state and does not claim that a public GitHub Release exists. See `docs/versions/v0.9.5.md`, `docs/versions/v0.9.4.md`, `docs/architecture/ui-design-system.md`, `docs/architecture/app-shell-settings.md`, `docs/architecture/metadata-editor.md`, `docs/architecture/content-labels.md` and `docs/architecture/variant-acceptance.md`.
