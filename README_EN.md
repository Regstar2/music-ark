# MusicArk

[Русский](README.md) · **English**

**Current code version: 0.11.1 — Bulk Upload, Recovery Sync & Explicit Scope Context.**  
**Current SQLite schema: 1.9.0.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. v0.11.0 proved production upload of one MP3; v0.11.1 keeps `YandexSingleTrackUploadService` as the only one-file transfer primitive and extends it into safe bulk upload and collection recovery.

## Bulk Upload & Recovery Sync v0.11.1

Local Library now selects tracks by stable `local_file_id`, supports Select all visible, a bulk toolbar and sequential upload (`concurrency=1`). The single-track upload action is no longer hidden in the overflow menu; it is a direct row action beside Play/Edit. Manual bulk upload defaults to the managed **UPLOADED TRACKS** playlist when configured.

MusicArk persists three managed playlist roles by playlist `kind`, not title: **CENSORED**, **UPLOADED TRACKS**, and **UNAVAILABLE**. Playlist creation stays fail-closed until a separate manual live proof succeeds; without that proof the user assigns existing owned playlists. CI never performs real playlist mutations.

Yandex provider availability is now independent from local Coverage: `available / unavailable / unknown`. Explicit `available=false` is evidence of unavailability; disappearance from a playlist alone is not. Lightweight last-known history tracks unavailable/available-again transitions without copying raw provider responses.

Controlled Sync can create `UPLOAD_LOCAL_TO_YANDEX` only for deterministic recovery: unavailable provider track + existing local MP3 → **UNAVAILABLE**; explicitly `censored` provider track + explicitly `original` local MP3 → **CENSORED**. `altered`, `different_version`, and `uncertain` do not prove censorship by themselves. Upload-only Sync does not require a download folder, but every upload apply requires fresh rights confirmation.

`YandexBatchUploadService` is not a second transport: every item calls `YandexSingleTrackUploadService`. One item failure does not stop safe later items; `delivery_unknown` is never blindly retried and requires playlist inspection first. Persistent upload mappings plus read-back make repeated Sync idempotent for verified uploads.

See `docs/versions/v0.11.1.md` for the full architecture, safety rules, research status, and limitations.

## Production Single-Track Yandex Upload v0.11.0

The confirmed v0.10.0 live result is:

```text
Stage 1 HTTP 200
Stage 2 HTTP 201
playlist read-back verified=true
ambiguous=false
attemptsUsed=1
```

Production Stage 1 uses the fixed endpoint:

```text
POST https://api.music.yandex.net/loader/upload-url
uid=<authenticated uid>
playlist-id=<uid>:<playlist kind>
path=<filename only>
```

MusicArk adds no `visibility`, Authorization, OAuth or Cookie. Stage 2 sends exactly one multipart `file` to the dynamic `post-target` after HTTPS/Yandex-host validation. HTTPX uses `http1=True`, `http2=True`, `trust_env=False`, `follow_redirects=False`, a bounded timeout and no automatic retry.

Local Library exposes an explicit **Upload to Yandex Music** action for one track. The user chooses an owned Yandex playlist and confirms the right to upload the file. The backend accepts `local_file_id`, resolves the indexed path itself, and before Stage 1 validates auth/UID, playlist ownership, an existing non-empty MP3 file, `confirm=true` and `rights_confirmed=true`.

After Stage 2 MusicArk performs bounded playlist read-back. A Stage 2 network failure **does not automatically send the file again**: MusicArk checks `ugc-track-id`; if delivery cannot be confirmed, it returns `delivery_unknown` and tells the user to inspect the playlist before retrying manually. This reduces the risk of duplicate UGC tracks.

`YandexMusicProvider.can_upload_tracks` and `supports_user_uploads` are now `true`, while Controlled Sync still generates no upload operations. The old `experimental_yandex_upload` remains a separate deprecated research/compatibility path and is not silently converted into the production mutation. Details are in `docs/versions/v0.11.0.md`.

v0.11.0 limitations: MP3 only, one track per action, no bulk upload, no upload queue, no auto-sync upload, no automatic retry, no format conversion, no censorship replacement and no background upload worker. This milestone does not create a production release or installer.

## Settings / Help / About v0.9.7

`Settings`, `Help` and `About` use a constrained responsive desktop composition instead of stretching sparse utility content across the whole workspace. Settings keeps the current System/Light/Dark and System/Russian/English preferences, places them in compact responsive cards, shows an auto-save status and renders a separate provider/account card from the existing `AccountSessionController`.

Help remains fully local and now contains 11 topics grouped into `Library / Collection analysis / Recovery and actions / Application`. It separately explains Identity/Metadata/Variant, Missing vs Different Version, ORIGINAL/CENSORED, Download states, Controlled Sync safety, the Metadata Editor write boundary, artwork/playback cache and diagnostic-data safety.

About reuses the existing `MusicArkMark`, presents version/environment data in a responsive grid, keeps safe diagnostic copy and standard Flutter dependency licenses, and exposes the GitHub repository. No URL-launch dependency is added: the repository remains selectable and has an explicit copy-link action. Help/About return to Settings inside the existing shell, so the Yandex workspace, account session and Now Playing are not recreated.

## Sync v0.9.6

`Sync` is presented as one sequential desktop workflow: scope and download-folder selection, status/summary, current and projected coverage, five primary metrics and one `Sync plan` with counted filters instead of several large `ExpansionTile` sections.

`All / Download / Decision / Matching / Version check / Local Library` filters operate only on operations already returned to Flutter and do not rebuild the backend plan. Wide layouts render operations as a table; narrow layouts use stacked rows. When the Sync payload has no artwork, a theme-aware local placeholder is used without an additional provider request.

Apply still rebuilds the current diff, requires explicit confirmation and uses the existing Sync bridge/DownloadService boundary. v0.9.6 adds no local-file deletion/move, metadata write, Yandex mutation, reverse sync or automatic Different Version replacement.

## Downloads v0.9.5

`Downloads` uses compact counted `Downloads` / `Wanted` tabs, separate summary metrics, search/status filters, compact lazy-rendered track rows and contextual bulk actions. User-facing failures are mapped from `errorCode`; the raw backend message plus task/provider/external IDs remain available separately in Technical details.

`failed` and `needs_review` tasks have an explicit `Remove` action. It deletes only the persisted download-task record; the final audio file, Local Library, Matching, Coverage, Wanted state, provider cache and audit history are not deleted. The expected sibling `.part` may be cleaned best-effort only after a safe-path check. `queued`/`running` tasks cannot be removed directly and continue to use cancellation.

Multi-selection supports retrying failed tasks, cancelling active tasks, removing failed tasks and `Download selected` in Wanted. The batch bridge sends ID sets through one Python process and returns partial results. `Retry selected` and `Download selected` execute only task IDs created or changed by the current action and do not wake unrelated old queue entries.

## Coverage / Missing v0.9.4

The `Missing` section centers the track list instead of a long technical statistics row. The page starts with a compact local-coverage card and progress meter, four primary metrics, collapsible Matching/Variant analysis details, counted status tabs and a responsive Collection/Search/Decision/Sort/Variant toolbar.

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

Downloads v0.9.5 and Sync v0.9.6 use a local placeholder when the current payload has no ready artwork; they add no per-row network artwork request.

## Content labels and Variant acceptance

App-level **ORIGINAL / CENSORED** marks can be stored for a local track and a cached Yandex identity. They do not mutate Yandex, rewrite audio metadata, change Matching identity or increase confidence.

For `ALTERED`, `DIFFERENT_VERSION` and `UNCERTAIN`, the user may accept the current recording and later undo that acceptance. The decision is stored separately from the analyzer result: the original Variant status does not become `SAME`. Acceptance remains valid only while the analysis evidence/fingerprint is unchanged.

## Formats

The editor uses format adapters. Full safe writing is implemented for **MP3/ID3**. Other audio formats remain read-only in Metadata Editor. Manual Yandex upload v0.11.0 is also MP3-only; format conversion is outside this milestone.

## Controlled Sync

Sync is not a bidirectional filesystem mirror. Normal Apply remains constrained to:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations from Controlled Sync = 0
```

v0.9.6 changes presentation only: plan filters operate on the already returned operation snapshot, while Apply still requires confirmation. Metadata Editor is a separate explicit-write workflow and is never called automatically by Scan/Matching/Coverage/Sync. Manual upload v0.11.0 is likewise a separate explicit workflow and is not invoked by SyncPlanner.

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

v0.10.0 and v0.11.0 do not bump the SQLite schema. Manual one-track upload adds no upload queue/history tables and never persists signed upload targets. Database initialization remains idempotent and does not require deleting an existing `.musicark/musicark.db`.

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
v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions    complete
v0.9.6 — Sync Page UI Polish                           complete
v0.9.7 — Settings, Help & About UI Polish              complete
v0.9.x — UI improvement line                           complete
v0.10.0 — Yandex Upload Feasibility / live proof       complete
v0.11.0 — Production Single-Track Yandex Upload        current
v0.12.0 — Upload queue / batch safety                  planned
```

v0.11.0 is the production boundary for manually uploading one MP3, not a GitHub Release. Bulk upload, upload queue, auto-sync upload, conversion and automatic retry remain outside this milestone. See `docs/versions/v0.11.0.md`.
