# Download Architecture — v0.7.0

## Boundary

v0.7 evolves the existing download subsystem instead of introducing a second queue or Yandex downloader.

```text
Flutter
  ↓
musicark.download.bridge
  ↓
DownloadService
  ├── CoverageRepository
  ├── DownloadStorageRepository
  ├── DownloadProviderRegistry
  │     └── YandexMusicDownloadProvider
  ├── LocalLibraryService
  │     └── LocalFileIndexer
  ├── MatchingStorageRepository
  └── SystemCredentialStore
```

The legacy `DownloadProviderRegistry` and `YandexMusicDownloadProvider` remain reusable. The legacy `DownloadSystem` is compatibility code only; production v0.7 orchestration lives in `DownloadService` because the old system stopped at a legacy local-file row and could leave `library_root_id = NULL`.

## Direct download intent vs triage

Coverage triage and direct acquisition are separate concepts.

Bulk intent remains:

```text
coverage_status = missing
user_action = wanted
```

A direct **Скачать** click does not require or persist `wanted`. The click itself is explicit user intent. `musicark.download.bridge` verifies the track is currently `missing`, creates/reuses the normal user task and persists `direct_request=true` in the safe task payload.

The existing `DownloadService` historically expects `userAction=wanted`. For a `direct_request` task, the bridge supplies an in-memory Coverage proxy that presents `wanted` only to that service call while the real `wanted / ignored / unreviewed` row in SQLite remains unchanged. The same scoped proxy is used for Retry.

This prevents direct downloading from changing the current `Решение` filter and unexpectedly removing Missing rows from the UI. After successful acquisition, the downloaded track still correctly leaves Missing because its derived Coverage becomes `covered`.

One active user task is allowed per download-provider identity `(yandex_music_download, external_id)`. Multiple Liked/playlist memberships therefore remain one queue item.

## Queue persistence and legacy isolation

The existing `download_tasks` table is extended in place by schema 1.7.0. New state includes downloaded/total bytes, cancellation flag, target root, error code, and update timestamp. Download settings persist both Local Library ownership and the exact folder selected by the user.

Lifecycle:

```text
queued → running → completed
               ↘ failed → retry → queued
               ↘ cancelled
queued → cancelled
queued → skipped
```

A process restart converts persisted v0.7 user `running` tasks to retryable `failed` with `error_code=interrupted`. No fake pause/resume state is presented.

The baseline worker is sequential (`max concurrency = 1`). This is a deliberate bounded-concurrency implementation; the queue can contain hundreds of entries without opening hundreds of transfers.

The SQLite table also contains historical/reference-acquisition tasks. `musicark.download.bridge` explicitly scopes the Downloads page, worker, recovery, retry/cancel and clear-history actions to v0.7 `provider_download` user tasks. Internal Variant reference-cache history is neither displayed nor executed/deleted by the user Downloads surface.

## v1.0 large-queue worker hardening

Windows acceptance with a ~5k queue exposed that the original Flutter loop started a fresh Python process for every `runTask` call. That also rebuilt `DownloadService` and initialized a new Yandex client for every track. A transient provider/session problem could therefore become thousands of process/client initializations and thousands of failed rows.

The v1.0 acceptance path keeps the persisted SQLite queue and the existing sequential UI loop, but `DownloadBridge.runTask()` now talks to one long-lived JSON-lines process:

```text
Flutter DownloadPage
  ↓ runTask(taskId) repeatedly
DownloadBridge
  ↓ one persistent Process.start(...)
musicark.download.worker_bridge
  ↓ one DownloadService
ResilientYandexMusicDownloadProvider
  ↓ one cached yandex_music.Client session
```

The worker process lives across sequential task requests. Closing the desktop application closes its stdin and terminates the worker; leaving Downloads stops the UI queue loop after the current request, so untouched rows remain `queued`. A later Continue can resume them.

`ResilientYandexMusicDownloadProvider` classifies authentication separately from provider/network failures and retries only transient transport/provider classes with bounded exponential backoff. HTTP 429 and transient 5xx responses receive distinct stable codes. Signed media URLs, OAuth tokens and response bodies never cross the bridge or enter persisted technical details.

The worker circuit breaker pauses execution immediately after an `authentication` failure and after three consecutive systemic provider/network failures. The pausing response terminates the worker process so the next explicit Continue starts a fresh service/client session. Permanent per-track failures such as `track_unavailable`, `no_download_info` and `ugc_unsupported` fail only that row and reset the systemic streak.

User-uploaded Yandex UUID identities are recognized explicitly. The current supported restore path does not claim that those UGC tracks are downloadable; they fail with `ugc_unsupported` rather than the misleading `invalid_track_id` code.

Bulk selected/retry actions remain one bounded Python process per explicit batch. The frozen runtime whitelists both `musicark.download.actions_bridge` and `musicark.download.worker_bridge`, so the same behavior is available from the portable/installed build rather than only from a developer checkout.

## Credentials and provider URLs

`DownloadService` obtains the Yandex token from `SystemCredentialStore` and passes it directly into `YandexMusicDownloadProvider`. The provider may retain legacy token fallback only for older tooling/reference workflows.

Forbidden persistent values include token, authorization/cookie data, and temporary direct download URLs. `DownloadStorageRepository` rejects sensitive task-payload keys. Direct links exist only in provider execution memory.

## Transfer

The provider resolves the exact requested Yandex track ID and chooses the highest available bitrate for `quality=best`. HTTP content is streamed directly to disk:

```text
<final>.part
   ↓ atomic promotion
<final>
```

When `Content-Length` exists, the provider reports real `(downloaded_bytes, total_bytes)`. Unknown total remains indeterminate. `DownloadService` throttles SQLite progress writes by time/byte thresholds.

Running cancellation is cooperative: the provider checks a callback between chunks. The callback reads the persisted cancellation flag at a bounded cadence. Cancellation/failure removes `.part`; v0.7 does not implement Range resume.

## Destination and path safety

The folder picker selects the **actual user download directory**. MusicArk persists that exact normalized path in `download_settings`; switching pages or recreating `DownloadService` must not replace it with a parent Local Library root or another derived path.

The selected folder must either be a Local Library root or lie under an existing root. If it is outside all configured roots, it becomes a Local Library root. Each task snapshots both `target_root_id` and exact `target_folder` at enqueue time so later settings changes do not move an already queued task.

Databases created before exact `target_path` persistence remain forward-compatible: an old root-only setting falls back to the historical `<root>/MusicArk` target until the user selects a folder again.

Filenames are sanitized for Windows reserved characters/names, trailing spaces/dots, and are kept as leaf names. The stable source ID is included:

```text
Artist - Title [yandex_123456].mp3
```

The provider resolves the final path and verifies its parent is the task target directory, preventing metadata-driven traversal.

## Post-download Local Library pipeline

HTTP success is not a terminal success condition.

```text
provider transfer
  ↓
non-empty atomic file
  ↓
LocalMetadataReader
  ↓
LocalFileIndexer.index_file(path, root)
  ↓
LocalLibraryStorageRepository.apply_scan(... allow_removals=False)
  ↓
local_audio_files with library_root_id + normalized_path + metadata
  ↓
MatchDecision(method=exact_id, confidence=1.0)
  ↓
MatchingStorageRepository.persist_batch
  ↓
CoverageRepository re-read
  ↓
covered
```

`LocalFileIndexer` indexes only the completed file and never performs a full root walk. It reuses the v0.4 metadata/storage path and disables removal reconciliation for this single-file operation.

The exact matching decision computes the global Local Library fingerprint *after* indexing, keeping v0.5 automatic-freshness semantics valid. No fuzzy candidate decision is needed because acquisition started from an exact provider identity.

Variant analysis is not invoked and no `SAME` result is manufactured.

## Reference cache separation

v0.5.1 reference files in `.musicark/downloads/yandex/` remain verification cache only. They are not v0.7 destinations, are not indexed into Local Library, cannot make Coverage `covered`, and are hidden from the v0.7 user Downloads history.

## Embedded playback boundary

Raw local paths are not permanently printed on track/download cards. They are shown only after an explicit **Показать путь** action.

For completed/local tracks the desktop UI exposes:

- **Воспроизвести** — route the local file into the application-wide MusicArk audio player;
- **Открыть расположение файла** — reveal/select the actual file in Explorer/Finder (or open its directory on Linux).

Playback never delegates to the OS default media application. `MusicArkAudioPlayer` owns one `media_kit` `Player` instance lazily and exposes a persistent Flutter Now Playing bar with play/pause, seek, position, duration, buffering/error state and stop controls. The player remains active while the user navigates between MusicArk sections.

`media_kit_libs_audio` supplies the audio-only native playback libraries. This avoids creating another media index: sources are the existing Local Library/download file paths.

## Bridge/UI boundary

Flutter receives only JSON task metadata and polls while a download worker is active. Binary download chunks never cross the Flutter↔Python boundary. Ordinary bridge actions continue to use `Process.run(..., runInShell: false)`; sequential `runTask` execution uses the persistent `musicark.download.worker_bridge` child process described above.

The Downloads page polls at 800 ms while queue execution is active and otherwise refreshes on demand. The queue/history page remains available for progress, cancellation, retry and diagnostics, but ordinary single-track download does not require visiting it.
